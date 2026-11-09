from models import ClinicAppointment, ClinicDocument, ClinicPatient, ClinicVisit
from util import age_from_dob


def patient_out(p: ClinicPatient) -> dict:
    return {
        "id": p.id,
        "fileNumber": p.fileNumber,
        "qrToken": p.qrToken,
        "isQuick": bool(p.isQuick),
        "name": p.name,
        "phone": p.phone,
        "dob": p.dob,
        # A stored age is only a fallback for files without a date of birth.
        "age": age_from_dob(p.dob) if p.dob else p.age,
        "gender": p.gender,
        "address": p.address,
        "bloodType": p.bloodType,
        "allergies": p.allergies,
        "chronicConditions": p.chronicConditions,
        "notes": p.notes,
        "bookingReference": p.bookingReference,
        "createdAt": p.createdAt,
        "updatedAt": p.updatedAt,
    }


def patient_brief(p: ClinicPatient | None) -> dict | None:
    if p is None:
        return None
    return {
        "id": p.id,
        "fileNumber": p.fileNumber,
        "isQuick": bool(p.isQuick),
        "name": p.name,
        "phone": p.phone,
        "age": age_from_dob(p.dob) if p.dob else p.age,
        "gender": p.gender,
        "allergies": p.allergies,
    }


def appointment_out(a: ClinicAppointment, patient: ClinicPatient | None = None) -> dict:
    out = {
        "id": a.id,
        "patientId": a.patient_id,
        "date": a.date,
        "time": a.time,
        "kind": a.kind,
        "status": a.status,
        "reason": a.reason,
        "queueNumber": a.queueNumber,
        "checkedInAt": a.checkedInAt,
        "visitId": a.visit_id,
        "hasIntake": bool(a.intake),
        "createdBy": a.createdBy,
        "createdAt": a.createdAt,
    }
    if patient is not None:
        out["patient"] = patient_brief(patient)
    return out


def visit_out(v: ClinicVisit) -> dict:
    return {
        "id": v.id,
        "patientId": v.patient_id,
        "appointmentId": v.appointment_id,
        "date": v.date,
        "doctor": v.doctor,
        "status": v.status,
        "diagnosis": v.diagnosis or "",
        "notes": v.notes or "",
        "soapNote": v.soapNote or {},
        "diagnostics": v.diagnostics or [],
        "treatments": v.treatments or [],
        "prescriptions": v.prescriptions or [],
        "followUpDate": v.followUpDate,
        "transcript": v.transcript or "",
        "audioFilename": v.audioFilename,
        "createdAt": v.createdAt,
        "updatedAt": v.updatedAt,
        "completedAt": v.completedAt,
    }


def document_out(d: ClinicDocument) -> dict:
    return {
        "id": d.id,
        "patientId": d.patient_id,
        "visitId": d.visit_id,
        "filename": d.filename,
        "originalName": d.originalName,
        "contentType": d.contentType,
        "uploadedBy": d.uploadedBy,
        "uploadedAt": d.uploadedAt,
    }
