from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import doctor_only
from database import get_db
from models import ClinicAppointment, ClinicVisit
from routers.patients import get_patient_or_404
from serializers import visit_out
from util import new_id, now_iso, today_iso

router = APIRouter(prefix="/api/visits", tags=["visits"], dependencies=[Depends(doctor_only)])


class StartVisitIn(BaseModel):
    patient_id: str
    appointment_id: Optional[str] = None


class VisitUpdate(BaseModel):
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    soapNote: Optional[dict[str, Any]] = None
    diagnostics: Optional[list[dict[str, Any]]] = None
    treatments: Optional[list[dict[str, Any]]] = None
    prescriptions: Optional[list[dict[str, Any]]] = None
    followUpDate: Optional[str] = None
    transcript: Optional[str] = None
    audioFilename: Optional[str] = None


class CompleteIn(BaseModel):
    # Book the follow-up appointment in the secretary's calendar.
    bookFollowUp: bool = True


def _get_visit(db: Session, visit_id: str) -> ClinicVisit:
    visit = db.get(ClinicVisit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


@router.post("/start")
def start_visit(body: StartVisitIn, db: Session = Depends(get_db), user: dict = Depends(doctor_only)):
    """Opens the visit the doctor works in. Reuses today's unfinished visit for
    this patient (so reopening the page never makes a duplicate) and links the
    patient's appointment for today, marking it "with the doctor"."""
    get_patient_or_404(db, body.patient_id)
    today = today_iso()

    appt = None
    if body.appointment_id:
        appt = db.get(ClinicAppointment, body.appointment_id)
        if not appt or appt.patient_id != body.patient_id:
            raise HTTPException(status_code=404, detail="Appointment not found")
    else:
        priority = {"in_progress": 0, "waiting": 1, "scheduled": 2}
        candidates = (
            db.query(ClinicAppointment)
            .filter(
                ClinicAppointment.patient_id == body.patient_id,
                ClinicAppointment.date == today,
                ClinicAppointment.status.in_(tuple(priority)),
            )
            .all()
        )
        appt = min(candidates, key=lambda a: priority[a.status], default=None)

    visit = None
    if appt and appt.visit_id:
        visit = db.get(ClinicVisit, appt.visit_id)
    if visit is None:
        visit = (
            db.query(ClinicVisit)
            .filter(ClinicVisit.patient_id == body.patient_id, ClinicVisit.status == "draft", ClinicVisit.date == today)
            .order_by(ClinicVisit.createdAt.desc())
            .first()
        )

    now = now_iso()
    if visit is None:
        visit = ClinicVisit(
            id=new_id(),
            patient_id=body.patient_id,
            appointment_id=appt.id if appt else None,
            date=today,
            doctor=user["name"],
            status="draft",
            createdAt=now,
            updatedAt=now,
        )
        db.add(visit)
    elif appt and not visit.appointment_id:
        visit.appointment_id = appt.id

    if appt and appt.status != "done":
        appt.status = "in_progress"
        appt.visit_id = visit.id
        if not appt.checkedInAt:
            appt.checkedInAt = now
        appt.updatedAt = now

    db.commit()
    return visit_out(visit)


@router.get("/{visit_id}")
def get_visit(visit_id: str, db: Session = Depends(get_db)):
    return visit_out(_get_visit(db, visit_id))


@router.put("/{visit_id}")
def save_visit(visit_id: str, body: VisitUpdate, db: Session = Depends(get_db)):
    visit = _get_visit(db, visit_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(visit, field, value)
    visit.updatedAt = now_iso()
    db.commit()
    return visit_out(visit)


@router.post("/{visit_id}/complete")
def complete_visit(visit_id: str, body: CompleteIn, db: Session = Depends(get_db), user: dict = Depends(doctor_only)):
    visit = _get_visit(db, visit_id)
    now = now_iso()
    visit.status = "completed"
    visit.completedAt = visit.completedAt or now
    visit.updatedAt = now

    if visit.appointment_id:
        appt = db.get(ClinicAppointment, visit.appointment_id)
        if appt:
            appt.status = "done"
            appt.updatedAt = now

    follow_up = None
    if body.bookFollowUp and visit.followUpDate and visit.followUpDate > today_iso():
        follow_up = (
            db.query(ClinicAppointment)
            .filter(
                ClinicAppointment.patient_id == visit.patient_id,
                ClinicAppointment.date == visit.followUpDate,
                ClinicAppointment.status.notin_(("cancelled",)),
            )
            .first()
        )
        if follow_up is None:
            follow_up = ClinicAppointment(
                id=new_id(),
                patient_id=visit.patient_id,
                date=visit.followUpDate,
                kind="follow_up",
                status="scheduled",
                reason=f"Follow-up: {visit.diagnosis}" if visit.diagnosis else "Follow-up",
                createdBy=user["name"],
                createdAt=now,
                updatedAt=now,
            )
            db.add(follow_up)

    db.commit()
    return {**visit_out(visit), "followUpAppointmentId": follow_up.id if follow_up else None}


@router.post("/{visit_id}/reopen")
def reopen_visit(visit_id: str, db: Session = Depends(get_db)):
    visit = _get_visit(db, visit_id)
    visit.status = "draft"
    visit.updatedAt = now_iso()
    db.commit()
    return visit_out(visit)


@router.delete("/{visit_id}")
def discard_visit(visit_id: str, db: Session = Depends(get_db)):
    """Throws away an unfinished visit and puts the patient back in line."""
    visit = _get_visit(db, visit_id)
    if visit.status != "draft" or visit.completedAt:
        raise HTTPException(status_code=409, detail="A completed visit can't be discarded")
    if visit.appointment_id:
        appt = db.get(ClinicAppointment, visit.appointment_id)
        if appt and appt.status == "in_progress":
            appt.status = "waiting"
            appt.visit_id = None
            appt.updatedAt = now_iso()
    db.delete(visit)
    db.commit()
    return {"ok": True}
