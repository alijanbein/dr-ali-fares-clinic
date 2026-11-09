from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import check_password, create_token, current_user
from database import get_db
from models import ClinicUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(ClinicUser).filter(func.lower(ClinicUser.email) == body.email.strip().lower()).first()
    if not user or not user.active or not check_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    return {
        "access_token": create_token(user),
        "user": {"email": user.email, "name": user.name, "role": user.role},
    }


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user
