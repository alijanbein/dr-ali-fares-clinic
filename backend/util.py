import secrets
import uuid
from datetime import datetime, timezone


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_iso() -> str:
    # The clinic works in local time — "today's appointments" means the
    # server's local date, not UTC's.
    return datetime.now().strftime("%Y-%m-%d")


def new_qr_token() -> str:
    return secrets.token_urlsafe(12)


def age_from_dob(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        born = datetime.strptime(dob[:10], "%Y-%m-%d")
    except ValueError:
        return None
    today = datetime.now()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
