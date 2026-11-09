from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from auth import doctor_only, staff
from database import get_db
from models import ClinicAppointment, ClinicDocument, ClinicPatient, ClinicVisit
from serializers import appointment_out, document_out, patient_out, visit_out
from util import new_id, new_qr_token, now_iso

router = APIRouter(prefix="/api/patients", tags=["patients"])

# What a scanned QR card contains: "CLINIC-PATIENT:<qrToken>".
QR_PREFIX = "CLINIC-PATIENT:"


class PatientIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    dob: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    bloodType: Optional[str] = None
    allergies: Optional[str] = None
    chronicConditions: Optional[str] = None
    notes: Optional[str] = None


def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def next_file_number(db: Session) -> str:
    """Sequential, human-friendly file numbers (C-00001, C-00002…)."""
    count = db.query(func.count(ClinicPatient.id)).scalar() or 0
    n = count + 1
    while True:
        candidate = f"C-{n:05d}"
        if not db.query(ClinicPatient.id).filter(ClinicPatient.fileNumber == candidate).first():
            return candidate
        n += 1


def create_patient(db: Session, data: dict, created_by: str | None, is_quick: bool = False) -> ClinicPatient:
    now = now_iso()
    patient = ClinicPatient(
        id=new_id(),
        fileNumber=next_file_number(db),
        qrToken=new_qr_token(),
        isQuick=is_quick,
        createdBy=created_by,
        createdAt=now,
        updatedAt=now,
        **{k: _clean(v) for k, v in data.items()},
    )
    db.add(patient)
    db.flush()
    return patient


def get_patient_or_404(db: Session, patient_id: str) -> ClinicPatient:
    patient = db.get(ClinicPatient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("")
def search_patients(
    q: str = "",
    quick_only: bool = False,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _user: dict = Depends(staff),
):
    query = db.query(ClinicPatient)
    term = q.strip()
    if term:
        if term.startswith(QR_PREFIX):
            term = term[len(QR_PREFIX):]
        like = f"%{term.lower()}%"
        query = query.filter(or_(
            func.lower(ClinicPatient.name).like(like),
            ClinicPatient.phone.like(f"%{term}%"),
            func.lower(ClinicPatient.fileNumber).like(like),
            ClinicPatient.qrToken == term,
        ))
    if quick_only:
        query = query.filter(ClinicPatient.isQuick.is_(True))
    patients = query.order_by(ClinicPatient.updatedAt.desc()).limit(limit).all()
    return [patient_out(p) for p in patients]


@router.get("/lookup")
def lookup(code: str, db: Session = Depends(get_db), _user: dict = Depends(staff)):
    """Exact match for a scanned QR card (or a typed file number)."""
    code = code.strip()
    if code.startswith(QR_PREFIX):
        code = code[len(QR_PREFIX):]
    patient = (
        db.query(ClinicPatient)
        .filter(or_(ClinicPatient.qrToken == code, func.upper(ClinicPatient.fileNumber) == code.upper()))
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="No patient matches this code")
    return patient_out(patient)


@router.post("")
def add_patient(body: PatientIn, db: Session = Depends(get_db), user: dict = Depends(staff)):
    if not _clean(body.name):
        raise HTTPException(status_code=422, detail="The patient's name is required")
    patient = create_patient(db, body.model_dump(), user["name"])
    db.commit()
    return patient_out(patient)


@router.get("/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db), _user: dict = Depends(staff)):
    patient = get_patient_or_404(db, patient_id)
    appointments = (
        db.query(ClinicAppointment)
        .filter(ClinicAppointment.patient_id == patient_id)
        .order_by(ClinicAppointment.date.desc(), ClinicAppointment.time.desc())
        .all()
    )
    return {**patient_out(patient), "appointments": [appointment_out(a) for a in appointments]}


@router.patch("/{patient_id}")
def update_patient(patient_id: str, body: PatientIn, db: Session = Depends(get_db), _user: dict = Depends(staff)):
    patient = get_patient_or_404(db, patient_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(patient, field, _clean(value))
    # A quick file becomes a normal one as soon as it has a name.
    if patient.isQuick and patient.name:
        patient.isQuick = False
    patient.updatedAt = now_iso()
    db.commit()
    return patient_out(patient)


@router.post("/{patient_id}/merge-into/{target_id}")
def merge_quick_patient(patient_id: str, target_id: str, db: Session = Depends(get_db), _user: dict = Depends(staff)):
    """A quick walk-in turned out to already have a file: move everything
    recorded under the placeholder onto the real file and delete it."""
    if patient_id == target_id:
        raise HTTPException(status_code=422, detail="Choose a different patient")
    source = get_patient_or_404(db, patient_id)
    target = get_patient_or_404(db, target_id)
    if not source.isQuick:
        raise HTTPException(status_code=422, detail="Only a quick (no-data) file can be merged")
    for model in (ClinicAppointment, ClinicVisit, ClinicDocument):
        db.query(model).filter(model.patient_id == source.id).update({"patient_id": target.id})
    target.updatedAt = now_iso()
    db.delete(source)
    db.commit()
    return patient_out(target)


@router.get("/{patient_id}/record")
def patient_record(patient_id: str, db: Session = Depends(get_db), _user: dict = Depends(doctor_only)):
    """Everything the doctor sees when opening a patient: file, visits,
    documents and appointments (with any pre-visit questionnaire)."""
    patient = get_patient_or_404(db, patient_id)
    visits = (
        db.query(ClinicVisit)
        .filter(ClinicVisit.patient_id == patient_id)
        .order_by(ClinicVisit.date.desc(), ClinicVisit.createdAt.desc())
        .all()
    )
    documents = (
        db.query(ClinicDocument)
        .filter(ClinicDocument.patient_id == patient_id)
        .order_by(ClinicDocument.uploadedAt.desc())
        .all()
    )
    appointments = (
        db.query(ClinicAppointment)
        .filter(ClinicAppointment.patient_id == patient_id)
        .order_by(ClinicAppointment.date.desc(), ClinicAppointment.time.desc())
        .all()
    )
    return {
        "patient": patient_out(patient),
        "visits": [visit_out(v) for v in visits],
        "documents": [document_out(d) for d in documents],
        "appointments": [{**appointment_out(a), "intake": a.intake} for a in appointments],
    }
