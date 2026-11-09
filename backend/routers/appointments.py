from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import staff
from database import get_db
from models import ClinicAppointment, ClinicPatient
from routers.patients import create_patient, get_patient_or_404
from serializers import appointment_out
from util import new_id, now_iso, today_iso

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

Kind = Literal["scheduled", "walk_in", "quick", "follow_up"]
Status = Literal["scheduled", "waiting", "in_progress", "done", "cancelled", "no_show"]

# Statuses the secretary sets by hand. "in_progress" and "done" are set by
# the doctor starting and completing the visit (see routers/visits.py).
SECRETARY_STATUSES = {"scheduled", "waiting", "cancelled", "no_show"}

# Board order: who's with the doctor, then the waiting line, then the rest.
STATUS_ORDER = {"in_progress": 0, "waiting": 1, "scheduled": 2, "done": 3, "no_show": 4, "cancelled": 5}


class AppointmentIn(BaseModel):
    patient_id: str
    date: str
    time: Optional[str] = None
    kind: Kind = "scheduled"
    reason: Optional[str] = None
    # Patient is already at the clinic: put them straight in the waiting line.
    checkIn: bool = False


class AppointmentUpdate(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[Status] = None


class QuickIn(BaseModel):
    reason: Optional[str] = None


def next_queue_number(db: Session, date: str) -> int:
    current = (
        db.query(func.max(ClinicAppointment.queueNumber))
        .filter(ClinicAppointment.date == date)
        .scalar()
    )
    return (current or 0) + 1


def check_in(db: Session, appt: ClinicAppointment) -> None:
    appt.status = "waiting"
    appt.checkedInAt = now_iso()
    if not appt.queueNumber:
        appt.queueNumber = next_queue_number(db, appt.date)


def sort_key(a: ClinicAppointment):
    # Waiting line by arrival; everything else by booked time.
    order = a.queueNumber if a.status == "waiting" and a.queueNumber else 0
    return (STATUS_ORDER.get(a.status, 9), order, a.time or "99:99", a.createdAt)


def with_patients(db: Session, appts: list[ClinicAppointment]) -> list[dict]:
    ids = {a.patient_id for a in appts}
    patients = {p.id: p for p in db.query(ClinicPatient).filter(ClinicPatient.id.in_(ids)).all()} if ids else {}
    return [appointment_out(a, patients.get(a.patient_id)) for a in appts]


@router.get("")
def list_appointments(
    date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(staff),
):
    query = db.query(ClinicAppointment)
    if date_from or date_to:
        if date_from:
            query = query.filter(ClinicAppointment.date >= date_from)
        if date_to:
            query = query.filter(ClinicAppointment.date <= date_to)
    else:
        query = query.filter(ClinicAppointment.date == (date or today_iso()))
    if status:
        query = query.filter(ClinicAppointment.status.in_(status.split(",")))
    appts = query.all()
    appts.sort(key=lambda a: (a.date, *sort_key(a)))
    return with_patients(db, appts)


@router.get("/summary")
def day_summary(date: Optional[str] = None, db: Session = Depends(get_db), _user: dict = Depends(staff)):
    day = date or today_iso()
    rows = (
        db.query(ClinicAppointment.status, func.count(ClinicAppointment.id))
        .filter(ClinicAppointment.date == day)
        .group_by(ClinicAppointment.status)
        .all()
    )
    counts = {s: 0 for s in STATUS_ORDER}
    counts.update({s: n for s, n in rows})
    counts["total"] = sum(n for s, n in rows if s != "cancelled")
    return {"date": day, "counts": counts}


@router.post("")
def create_appointment(body: AppointmentIn, db: Session = Depends(get_db), user: dict = Depends(staff)):
    get_patient_or_404(db, body.patient_id)
    now = now_iso()
    appt = ClinicAppointment(
        id=new_id(),
        patient_id=body.patient_id,
        date=body.date,
        time=(body.time or None),
        kind=body.kind,
        status="scheduled",
        reason=(body.reason or "").strip() or None,
        createdBy=user["name"],
        createdAt=now,
        updatedAt=now,
    )
    db.add(appt)
    if body.checkIn:
        check_in(db, appt)
    db.commit()
    return with_patients(db, [appt])[0]


@router.post("/quick")
def quick_appointment(body: QuickIn, db: Session = Depends(get_db), user: dict = Depends(staff)):
    """One click: a placeholder patient with no data goes straight into the
    doctor's waiting line. The secretary completes the file later."""
    today = today_iso()
    queue = next_queue_number(db, today)
    patient = create_patient(db, {}, user["name"], is_quick=True)
    now = now_iso()
    appt = ClinicAppointment(
        id=new_id(),
        patient_id=patient.id,
        date=today,
        kind="quick",
        status="waiting",
        reason=(body.reason or "").strip() or None,
        queueNumber=queue,
        checkedInAt=now,
        createdBy=user["name"],
        createdAt=now,
        updatedAt=now,
    )
    db.add(appt)
    db.commit()
    return with_patients(db, [appt])[0]


@router.patch("/{appointment_id}")
def update_appointment(appointment_id: str, body: AppointmentUpdate, db: Session = Depends(get_db), user: dict = Depends(staff)):
    appt = db.get(ClinicAppointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    changes = body.model_dump(exclude_unset=True)
    status = changes.pop("status", None)
    for field, value in changes.items():
        setattr(appt, field, (value.strip() or None) if isinstance(value, str) else value)
    if status and status != appt.status:
        if user["role"] == "secretary" and status not in SECRETARY_STATUSES:
            raise HTTPException(status_code=403, detail="Only the doctor can start or finish a visit")
        if appt.status in ("in_progress", "done") and user["role"] != "doctor":
            raise HTTPException(status_code=409, detail="This patient is already with the doctor")
        if status == "waiting":
            check_in(db, appt)
        else:
            appt.status = status
    appt.updatedAt = now_iso()
    db.commit()
    return with_patients(db, [appt])[0]


@router.post("/{appointment_id}/check-in")
def check_in_appointment(appointment_id: str, db: Session = Depends(get_db), _user: dict = Depends(staff)):
    appt = db.get(ClinicAppointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.status not in ("scheduled", "no_show"):
        raise HTTPException(status_code=409, detail="This appointment can't be checked in")
    # Checking in a future booking means the patient came today.
    appt.date = today_iso()
    appt.queueNumber = None
    check_in(db, appt)
    appt.updatedAt = now_iso()
    db.commit()
    return with_patients(db, [appt])[0]
