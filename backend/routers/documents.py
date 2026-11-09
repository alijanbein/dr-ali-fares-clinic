import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth import current_user_header_or_query, doctor_only
from database import get_db
from models import ClinicDocument
from routers.patients import get_patient_or_404
from serializers import document_out
from util import new_id, now_iso

router = APIRouter(tags=["documents"])

DOCS_DIR = Path(__file__).resolve().parent.parent / "documents"
DOCS_DIR.mkdir(exist_ok=True)

ALLOWED = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".pdf": "application/pdf"}
MAX_BYTES = 20 * 1024 * 1024


@router.post("/api/patients/{patient_id}/documents")
async def upload_document(
    patient_id: str,
    file: UploadFile = File(...),
    visit_id: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(doctor_only),
):
    get_patient_or_404(db, patient_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(status_code=422, detail="Only images (JPG, PNG, WEBP) and PDF files can be attached")
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 20 MB")
    filename = f"{uuid.uuid4()}{suffix}"
    (DOCS_DIR / filename).write_bytes(content)
    doc = ClinicDocument(
        id=new_id(),
        patient_id=patient_id,
        visit_id=visit_id or None,
        filename=filename,
        originalName=file.filename or filename,
        contentType=ALLOWED[suffix],
        uploadedBy=user["name"],
        uploadedAt=now_iso(),
    )
    db.add(doc)
    db.commit()
    return document_out(doc)


@router.delete("/api/documents/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db), _user: dict = Depends(doctor_only)):
    doc = db.get(ClinicDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    path = DOCS_DIR / doc.filename
    db.delete(doc)
    db.commit()
    path.unlink(missing_ok=True)
    return {"ok": True}


@router.get("/api/files/{filename}")
def get_file(filename: str, user: dict = Depends(current_user_header_or_query)):
    if user["role"] != "doctor":
        raise HTTPException(status_code=403, detail="Not allowed")
    path = (DOCS_DIR / filename).resolve()
    if path.parent != DOCS_DIR.resolve() or not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type=ALLOWED.get(path.suffix.lower(), "application/octet-stream"))
