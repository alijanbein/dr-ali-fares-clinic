"""End-to-end flow on a temporary SQLite database (never the real one).
Run: python -m pytest tests"""
import os
import tempfile

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"
os.environ.setdefault("OPENAI_API_KEY", "test")

from fastapi.testclient import TestClient  # noqa: E402

import create_user  # noqa: E402
from database import SessionLocal, ensure_tables  # noqa: E402
from main import app  # noqa: E402
from util import today_iso  # noqa: E402

client = TestClient(app)


def _login(email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def setup_module():
    ensure_tables()
    db = SessionLocal()
    create_user.upsert(db, "doc@test", "Doc", "doctor", "docpass")
    create_user.upsert(db, "sec@test", "Sec", "secretary", "secpass")
    db.close()


def test_full_clinic_flow():
    sec = _login("sec@test", "secpass")
    doc = _login("doc@test", "docpass")

    # Secretary: new patient + appointment checked in today.
    p = client.post("/api/patients", json={"name": "Ahmad Saleh", "phone": "0791234567", "dob": "1980-05-01"}, headers=sec).json()
    assert p["fileNumber"].startswith("C-") and p["age"] >= 45
    a = client.post("/api/appointments", json={"patient_id": p["id"], "date": today_iso(), "time": "10:00", "checkIn": True}, headers=sec).json()
    assert a["status"] == "waiting" and a["queueNumber"] == 1

    # Quick walk-in with no data goes straight to the waiting line.
    q = client.post("/api/appointments/quick", json={}, headers=sec).json()
    assert q["status"] == "waiting" and q["patient"]["isQuick"] and q["queueNumber"] == 2

    # Secretary can't read clinical data or start a visit.
    assert client.get(f"/api/patients/{p['id']}/record", headers=sec).status_code == 403
    assert client.post("/api/visits/start", json={"patient_id": p["id"]}, headers=sec).status_code == 403
    assert client.patch(f"/api/appointments/{a['id']}", json={"status": "done"}, headers=sec).status_code == 403

    # Doctor finds the patient by QR payload and by search.
    found = client.get("/api/patients/lookup", params={"code": f"CLINIC-PATIENT:{p['qrToken']}"}, headers=doc).json()
    assert found["id"] == p["id"]
    assert client.get("/api/patients", params={"q": "ahmad"}, headers=doc).json()[0]["id"] == p["id"]

    # Start → save → complete with follow-up booking.
    v = client.post("/api/visits/start", json={"patient_id": p["id"]}, headers=doc).json()
    again = client.post("/api/visits/start", json={"patient_id": p["id"]}, headers=doc).json()
    assert again["id"] == v["id"]
    board = client.get("/api/appointments", headers=sec).json()
    assert board[0]["id"] == a["id"] and board[0]["status"] == "in_progress"

    client.put(f"/api/visits/{v['id']}", json={
        "diagnosis": "Knee OA", "soapNote": {"assessment": "Knee OA"},
        "prescriptions": [{"name": "Ibuprofen", "dose": "400 mg"}], "followUpDate": "2099-01-15",
    }, headers=doc)
    done = client.post(f"/api/visits/{v['id']}/complete", json={"bookFollowUp": True}, headers=doc).json()
    assert done["status"] == "completed" and done["followUpAppointmentId"]
    rec = client.get(f"/api/patients/{p['id']}/record", headers=doc).json()
    assert rec["visits"][0]["diagnosis"] == "Knee OA"
    assert any(x["kind"] == "follow_up" and x["date"] == "2099-01-15" for x in rec["appointments"])

    # Quick file merged into the real one moves its appointment.
    m = client.post(f"/api/patients/{q['patient']['id']}/merge-into/{p['id']}", headers=sec)
    assert m.status_code == 200
    assert len(client.get(f"/api/patients/{p['id']}", headers=sec).json()["appointments"]) == 3

    # Website inbox degrades cleanly when the website table isn't here.
    assert client.get("/api/booking-requests", headers=sec).json()["available"] is False


def test_bad_login_and_no_token():
    assert client.post("/api/auth/login", json={"email": "sec@test", "password": "x"}).status_code == 401
    assert client.get("/api/patients").status_code == 401
