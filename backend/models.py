"""The clinic's own tables. Every table is prefixed `clinic_` so it can live in
the hospital's database for now without touching any hospital table."""
from sqlalchemy import JSON, Boolean, Column, Integer, String, Text

from database import Base


class ClinicUser(Base):
    __tablename__ = "clinic_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # doctor | secretary
    password_hash = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    createdAt = Column(String, nullable=False)


class ClinicPatient(Base):
    """A patient's file. A *quick* patient is a placeholder the secretary
    creates with one click so someone can see the doctor right away; their
    details are filled in (or merged into an existing file) afterwards."""
    __tablename__ = "clinic_patients"

    id = Column(String, primary_key=True)
    fileNumber = Column(String, nullable=False, unique=True, index=True)
    # Printed on the patient's card as a QR code. Random, so the code on a
    # card can't be guessed from the file number.
    qrToken = Column(String, nullable=False, unique=True, index=True)
    isQuick = Column(Boolean, nullable=False, default=False)

    name = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True, index=True)
    dob = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    address = Column(String, nullable=True)
    bloodType = Column(String, nullable=True)
    allergies = Column(String, nullable=True)
    chronicConditions = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Website booking request this file was created from, if any.
    bookingReference = Column(String, nullable=True)
    createdBy = Column(String, nullable=True)
    createdAt = Column(String, nullable=False)
    updatedAt = Column(String, nullable=False)


class ClinicAppointment(Base):
    __tablename__ = "clinic_appointments"

    id = Column(String, primary_key=True)
    patient_id = Column(String, nullable=False, index=True)
    date = Column(String, nullable=False, index=True)  # YYYY-MM-DD
    time = Column(String, nullable=True)  # HH:MM, empty for walk-ins
    # scheduled | walk_in | quick | follow_up
    kind = Column(String, nullable=False, default="scheduled")
    # scheduled | waiting | in_progress | done | cancelled | no_show
    status = Column(String, nullable=False, default="scheduled", index=True)
    reason = Column(Text, nullable=True)
    # Order of arrival for the day, given at check-in.
    queueNumber = Column(Integer, nullable=True)
    checkedInAt = Column(String, nullable=True)
    visit_id = Column(String, nullable=True)
    # Pre-visit questionnaire copied from a website booking request.
    intake = Column(JSON, nullable=True)
    createdBy = Column(String, nullable=True)
    createdAt = Column(String, nullable=False)
    updatedAt = Column(String, nullable=False)


class ClinicVisit(Base):
    """One consultation with the doctor: the same note the hospital OPD
    produces (SOAP, diagnosis, tests ordered, treatment plan) plus the
    prescription. No surgical/operative notes in the clinic."""
    __tablename__ = "clinic_visits"

    id = Column(String, primary_key=True)
    patient_id = Column(String, nullable=False, index=True)
    appointment_id = Column(String, nullable=True, index=True)
    date = Column(String, nullable=False)
    doctor = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")  # draft | completed

    diagnosis = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    soapNote = Column(JSON, nullable=True)
    # [{type, status: ordered|resulted, result}]
    diagnostics = Column(JSON, nullable=True)
    # [{type, duration, details, followUpDate}]
    treatments = Column(JSON, nullable=True)
    # [{name, dose, frequency, duration, instructions}]
    prescriptions = Column(JSON, nullable=True)
    followUpDate = Column(String, nullable=True)

    transcript = Column(Text, nullable=True)
    audioFilename = Column(String, nullable=True)

    createdAt = Column(String, nullable=False)
    updatedAt = Column(String, nullable=False)
    completedAt = Column(String, nullable=True)


class ClinicDocument(Base):
    """An image or PDF the doctor attaches to a patient (X-ray, MRI report…)."""
    __tablename__ = "clinic_documents"

    id = Column(String, primary_key=True)
    patient_id = Column(String, nullable=False, index=True)
    visit_id = Column(String, nullable=True, index=True)
    filename = Column(String, nullable=False)
    originalName = Column(String, nullable=False)
    contentType = Column(String, nullable=False)
    uploadedBy = Column(String, nullable=True)
    uploadedAt = Column(String, nullable=False)
