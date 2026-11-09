# Clinic system (doctor + secretary)

The in-clinic system for the doctor's private practice. Shorter than the
hospital OPD (`../orthopedic-opd-ai-test`): no surgery / operative notes, no
nurse or PROM follow-up calls. Two portals, two accounts:

| Portal | Can do | Can't do |
| --- | --- | --- |
| **Secretary** (`/s/...`) | Patients (create, edit, QR card), appointments (book, check in, reschedule, cancel, no-show), **quick patient** (no data, straight to the doctor), merge a quick file into an existing one, website booking requests | Read clinical notes, dictation, files, start/finish visits |
| **Doctor** (`/d/...`) | Today's queue, find a patient by search / QR scan / file number, full record, dictate the visit (AI fills SOAP, tests, treatment plan, follow-up), prescription, attach images/PDFs, print report or prescription, complete visit (books the follow-up for the secretary) | — |

## Run

```bat
backend\start_backend.bat     :: http://localhost:8002
start_frontend.bat            :: http://localhost:5190
```

## Accounts

Created with `python create_user.py --defaults` (prints generated passwords once).

- `doctor@clinic.local` — role `doctor`
- `secretary@clinic.local` — role `secretary`

Reset a password / add an account:

```bash
cd backend
python create_user.py --email doctor@clinic.local --role doctor --name "Dr. Ali Fares" --password "new-password"
```

## Settings (`backend/.env`)

| Name | Purpose |
| --- | --- |
| `DATABASE_URL` | For now the hospital's database. Only `clinic_*` tables are created/used. |
| `OPENAI_API_KEY`, `OPENAI_TRANSCRIBE_MODEL` | Same key and transcription model as the hospital system. |
| `OPENAI_EXTRACT_MODEL` | `gpt-4o-mini`, structures the dictation (same as the hospital). |
| `CLINIC_JWT_SECRET` | Signs login sessions. Clinic tokens are not accepted by the hospital API and vice versa. |
| `ALLOWED_ORIGINS` | Frontend address(es). |

Frontend (`frontend/.env`, optional): `VITE_API_BASE_URL` (default: same host, port 8002),
`VITE_CLINIC_NAME` (printed on reports).

## Moving to its own database later

1. Copy the five tables `clinic_users`, `clinic_patients`, `clinic_appointments`,
   `clinic_visits`, `clinic_documents` to the new database.
2. Change `DATABASE_URL`.

The website-requests inbox reads `doctor_booking_requests` (owned by
`../doctor-backend`) directly while both share a database. After the move it
shows "not connected" until it is pointed at that backend's API instead.

## How the pieces fit

- **Quick patient**: one click creates an empty file (`isQuick`) + a waiting
  appointment. The doctor sees "Quick patient · C-000xx" and works normally;
  the secretary later fills the details or merges it into the real file.
- **QR card**: each file has a random `qrToken`; the card encodes
  `CLINIC-PATIENT:<token>`. The doctor scans with the camera (needs https or
  localhost), a USB scanner into the search box, or types the file number.
- **Dictation**: `backend/llm_extract.py` is a copy of the hospital's — keep
  both in sync if one changes.
- Queue and appointment board refresh every 15 s, so both rooms stay in step.

## Tests

```bash
cd backend
python -m pytest tests      # temporary SQLite, never touches DATABASE_URL
```

## Known limits

- English UI only (the dictation itself understands English, Arabic, French).
- Audio and attached files are stored on the server's disk (`backend/audio`,
  `backend/documents`), not in the database — back those folders up too.
- Prescriptions are typed by the doctor; dictation fills the treatment plan,
  not individual drug lines.
