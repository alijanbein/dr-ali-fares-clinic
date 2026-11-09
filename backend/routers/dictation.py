"""Voice dictation for the doctor — the same pipeline as the hospital OPD
(backend/main.py there): OpenAI transcription (OPENAI_TRANSCRIBE_MODEL) and
structuring into SOAP / tests / treatments with OPENAI_EXTRACT_MODEL
(gpt-4o-mini) via llm_extract.py. Only the physician note type is offered;
the clinic has no operative notes."""
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from openai import OpenAI

from auth import current_user_header_or_query, doctor_only
from llm_extract import DIAGNOSTIC_TESTS, TREATMENT_OPTIONS, detect_language, extract_structured
from util import now_iso

router = APIRouter(tags=["dictation"])

AUDIO_DIR = Path(__file__).resolve().parent.parent / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LANGUAGE_NAMES = {"en": "English", "ar": "Arabic", "fr": "French", "mixed": "Arabic-English"}
FORCEABLE_LANGUAGES = {"en", "ar", "fr"}

CLINICAL_VOCAB_PROMPTS = {
    "en": (
        "Diagnosis. Diagnostics. Treatment plan. "
        "Osteoarthritis, rotator cuff tear, ACL tear, meniscus tear, herniated disc, "
        "lumbar disc herniation, sciatica, fracture, dislocation, tendinitis, bursitis, "
        "carpal tunnel syndrome, scoliosis, spinal stenosis. "
        "X-ray, MRI, CT scan, ultrasound, laboratory tests. "
        "Medication, physiotherapy, injection therapy, corticosteroid, "
        "rest and monitoring, long-term rehabilitation, follow-up."
    ),
    "ar": (
        "التشخيص. الفحوصات. خطة العلاج. "
        "خشونة المفاصل، تمزق الكفة المدورة، تمزق الرباط الصليبي، تمزق الغضروف الهلالي، انزلاق غضروفي، "
        "عرق النسا، كسر، خلع، التهاب الأوتار، التهاب الجراب، متلازمة النفق الرسغي، الجنف، ضيق القناة الشوكية. "
        "أشعة سينية، رنين مغناطيسي، أشعة مقطعية، موجات فوق صوتية، تحاليل مخبرية. "
        "دواء، علاج طبيعي، حقن، كورتيزون، راحة ومتابعة، إعادة تأهيل طويلة الأمد، موعد متابعة."
    ),
    "fr": (
        "Diagnostic. Examens. Plan de traitement. "
        "Arthrose, déchirure de la coiffe des rotateurs, rupture du ligament croisé, déchirure méniscale, hernie discale, "
        "sciatique, fracture, luxation, tendinite, bursite, syndrome du canal carpien, scoliose, sténose spinale. "
        "Radiographie, IRM, scanner, échographie, analyses de laboratoire. "
        "Médicament, kinésithérapie, injection, corticoïde, repos et surveillance, "
        "rééducation à long terme, rendez-vous de suivi."
    ),
}


def run_transcription(path: str, language: str | None = None) -> str:
    with open(path, "rb") as f:
        kwargs = {"model": OPENAI_TRANSCRIBE_MODEL, "file": f, "response_format": "json"}
        # Code-switched speech gets neither a forced language nor a one-language
        # vocabulary prompt, which would pull the other language's words over.
        if language != "mixed":
            kwargs["prompt"] = CLINICAL_VOCAB_PROMPTS.get(language, CLINICAL_VOCAB_PROMPTS["en"])
        if language in FORCEABLE_LANGUAGES:
            kwargs["language"] = language
        response = _client.audio.transcriptions.create(**kwargs)
    return response.text.strip()


def transcribe_with_fallback(path: str, language: str | None = None) -> str:
    """Retries once through an ffmpeg re-encode: the browser's chunked WebM is
    occasionally a container the API rejects even though the audio is fine."""
    try:
        return run_transcription(path, language)
    except Exception as e:
        print(f"Transcription rejected the raw upload ({e}); retrying via ffmpeg re-encode", flush=True)
        from pydub import AudioSegment

        reencoded = path + "_reencoded.wav"
        AudioSegment.from_file(path).export(reencoded, format="wav")
        try:
            return run_transcription(reencoded, language)
        finally:
            os.unlink(reencoded)


def _suffix(upload: UploadFile) -> str:
    suffix = os.path.splitext(upload.filename or "")[-1].lower()
    return suffix if suffix in (".webm", ".ogg", ".wav", ".mp3", ".m4a") else ".webm"


@router.get("/api/options")
def options(_user: dict = Depends(doctor_only)):
    """The fixed lists the dictation maps speech onto."""
    return {
        "diagnosticTests": [{"id": k, "name": v} for k, v in DIAGNOSTIC_TESTS.items()],
        "treatmentOptions": [{"id": k, "name": v} for k, v in TREATMENT_OPTIONS.items()],
    }


@router.post("/api/transcribe/preview")
async def transcribe_preview(
    audio: UploadFile = File(...),
    language: str = Form(default=""),
    _user: dict = Depends(doctor_only),
):
    """Live caption of the recording so far. The first call detects the
    language from the first words; later calls force it."""
    had_language = language in LANGUAGE_NAMES
    with tempfile.NamedTemporaryFile(delete=False, suffix=_suffix(audio)) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        text = run_transcription(tmp_path, language if had_language else None)
        return {"text": text, "language": language if had_language else detect_language(text)}
    except Exception as e:
        # A mid-recording chunk can be momentarily undecodable; the caption
        # just skips a beat.
        return {"text": "", "language": None, "warning": str(e)}
    finally:
        os.unlink(tmp_path)


@router.post("/api/dictate")
async def dictate(
    audio: UploadFile = File(...),
    language: str = Form(default=""),
    _user: dict = Depends(doctor_only),
):
    had_language = language in LANGUAGE_NAMES
    suffix = _suffix(audio)
    content = await audio.read()

    audio_filename = f"{uuid.uuid4()}{suffix}"
    (AUDIO_DIR / audio_filename).write_bytes(content)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        try:
            text = transcribe_with_fallback(tmp_path, language if had_language else None)
        except Exception as e:
            return JSONResponse(status_code=422, content={"detail": f"Could not process the recording: {e}"})
        code = language if had_language else detect_language(text)
        return {
            "text": text,
            "language": code,
            "languageName": LANGUAGE_NAMES.get(code, "Unknown"),
            "structured": extract_structured(text, note_type="physician"),
            "audioFilename": audio_filename,
            "timestamp": now_iso(),
        }
    finally:
        os.unlink(tmp_path)


@router.get("/api/audio/{filename}")
def get_audio(filename: str, user: dict = Depends(current_user_header_or_query)):
    if user["role"] != "doctor":
        return JSONResponse(status_code=403, content={"detail": "Not allowed"})
    path = (AUDIO_DIR / filename).resolve()
    if path.parent != AUDIO_DIR.resolve() or not path.exists():
        return JSONResponse(status_code=404, content={"detail": "Recording not found"})
    media = {".webm": "audio/webm", ".ogg": "audio/ogg", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}
    return FileResponse(path, media_type=media.get(path.suffix, "application/octet-stream"))
