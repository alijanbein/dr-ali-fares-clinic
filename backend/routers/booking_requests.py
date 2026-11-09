"""Appointment requests sent from the doctor's website (stored by
../doctor-backend in `doctor_booking_requests`, in the same database for now).
The secretary turns a request into a clinic file + appointment; its
pre-visit questionnaire travels with the appointment so the doctor sees it.

This module reads that table with plain SQL and never creates it. If the
clinic moves to its own database, this inbox simply reports itself as
unavailable until it is pointed at the website's API instead."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from auth import staff
from database import get_db, table_exists
from models import ClinicAppointment, ClinicPatient
from routers.patients import create_patient, get_patient_or_404
from serializers import appointment_out
from util import new_id, now_iso

router = APIRouter(prefix="/api/booking-requests", tags=["website requests"])

TABLE = "doctor_booking_requests"
COLUMNS = (
    'reference, status, "createdAt", language, name, age, gender, phone, "contactMethod", '
    '"bodyArea", side, "chiefComplaint", onset, mechanism, history, "redFlags", urgent, '
    '"promName", answers, "painScore", "finalScore", "scoreDirection", interpretation, '
    '"preferredDate", "preferredTime", notes, "secretaryNote"'
)


class ScheduleIn(BaseModel):
    date: str
    time: Optional[str] = None
    # Attach to an existing file instead of creating a new one.
    patient_id: Optional[str] = None


def _row_out(row) -> dict:
    d = dict(row._mapping)
    created = d.get("createdAt")
    if isinstance(created, datetime):
        d["createdAt"] = created.astimezone(timezone.utc).isoformat() if created.tzinfo else created.isoformat()
    return d


def _require_table():
    if not table_exists(TABLE):
        raise HTTPException(status_code=404, detail="Website requests aren't available in this database")


@router.get("")
def list_requests(status: str = "new,contacted", db: Session = Depends(get_db), _user: dict = Depends(staff)):
    if not table_exists(TABLE):
        return {"available": False, "items": []}
    statuses = [s for s in status.split(",") if s]
    stmt = text(
        f'SELECT {COLUMNS} FROM {TABLE} WHERE status IN :statuses ORDER BY urgent DESC, "createdAt" DESC LIMIT 200'
    ).bindparams(bindparam("statuses", expanding=True))
    rows = db.execute(stmt, {"statuses": statuses}).fetchall()
    return {"available": True, "items": [_row_out(r) for r in rows]}


@router.post("/{reference}/schedule")
def schedule_request(reference: str, body: ScheduleIn, db: Session = Depends(get_db), user: dict = Depends(staff)):
    _require_table()
    row = db.execute(text(f"SELECT {COLUMNS} FROM {TABLE} WHERE reference = :ref"), {"ref": reference}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    req = _row_out(row)

    if body.patient_id:
        patient = get_patient_or_404(db, body.patient_id)
    else:
        patient = (
            db.query(ClinicPatient)
            .filter(ClinicPatient.phone == req["phone"], ClinicPatient.name == req["name"])
            .first()
        )
        if patient is None:
            patient = create_patient(
                db,
                {
                    "name": req["name"],
                    "phone": req["phone"],
                    "age": req["age"],
                    "gender": (req["gender"] or "").capitalize() or None,
                },
                user["name"],
            )
            patient.bookingReference = reference

    intake = {
        "source": "website",
        "reference": reference,
        "bodyArea": req["bodyArea"],
        "side": req["side"],
        "chiefComplaint": req["chiefComplaint"],
        "onset": req["onset"],
        "mechanism": req["mechanism"],
        "history": req["history"],
        "redFlags": req["redFlags"],
        "urgent": req["urgent"],
        "promName": req["promName"],
        "answers": req["answers"],
        "painScore": req["painScore"],
        "finalScore": req["finalScore"],
        "scoreDirection": req["scoreDirection"],
        "interpretation": req["interpretation"],
        "notes": req["notes"],
    }
    now = now_iso()
    appt = ClinicAppointment(
        id=new_id(),
        patient_id=patient.id,
        date=body.date,
        time=body.time or None,
        kind="scheduled",
        status="scheduled",
        reason=req["chiefComplaint"],
        intake=intake,
        createdBy=user["name"],
        createdAt=now,
        updatedAt=now,
    )
    db.add(appt)
    db.execute(
        text(f'UPDATE {TABLE} SET status = :status, "updatedAt" = :now WHERE reference = :ref'),
        {"status": "booked", "now": datetime.now(timezone.utc), "ref": reference},
    )
    db.commit()
    return appointment_out(appt, patient)


@router.post("/{reference}/close")
def close_request(reference: str, db: Session = Depends(get_db), _user: dict = Depends(staff)):
    _require_table()
    result = db.execute(
        text(f'UPDATE {TABLE} SET status = :status, "updatedAt" = :now WHERE reference = :ref'),
        {"status": "closed", "now": datetime.now(timezone.utc), "ref": reference},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Request not found")
    db.commit()
    return {"ok": True}
