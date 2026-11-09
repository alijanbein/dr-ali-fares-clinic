import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Query
from dotenv import load_dotenv
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

SECRET_KEY = os.getenv("CLINIC_JWT_SECRET") or os.getenv("JWT_SECRET") or "clinic-dev-secret-change-me"
ALGORITHM = "HS256"
TOKEN_MINUTES = 60 * 12  # one working day
# Tagged so a hospital staff token (same secret, no audience) or a hospital
# patient token is never accepted here, and a clinic token never works there.
AUDIENCE = "clinic"

ROLES = ("doctor", "secretary")

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user) -> str:
    payload = {
        "sub": user.email,
        "uid": user.id,
        "name": user.name,
        "role": user.role,
        "aud": AUDIENCE,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode(raw: str | None) -> dict:
    if not raw:
        raise HTTPException(status_code=401, detail="Not signed in")
    try:
        payload = jwt.decode(raw, SECRET_KEY, algorithms=[ALGORITHM], audience=AUDIENCE)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid session")
    if payload.get("role") not in ROLES:
        raise HTTPException(status_code=401, detail="Invalid session")
    return {"email": payload["sub"], "id": payload.get("uid"), "name": payload.get("name"), "role": payload["role"]}


def current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    return _decode(credentials.credentials if credentials else None)


def current_user_header_or_query(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    token: str = Query(default=None),
) -> dict:
    """For files opened directly by <audio src> / <a href>, which can't send
    an Authorization header."""
    return _decode(credentials.credentials if credentials else token)


def require(*roles):
    def checker(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Your account doesn't have access to this")
        return user
    return checker


doctor_only = require("doctor")
staff = require("doctor", "secretary")
