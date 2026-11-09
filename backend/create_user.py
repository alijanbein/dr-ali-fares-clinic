"""Create or reset a clinic account.

    python create_user.py --defaults
        Creates the doctor and secretary accounts if they don't exist yet and
        prints their generated passwords (shown once — write them down).

    python create_user.py --email doctor@clinic.local --role doctor --name "Dr. Ali Fares"
        Creates the account, or resets its password if it exists. Add
        --password to choose it; otherwise one is generated and printed.
"""
import argparse
import secrets

from auth import ROLES, hash_password
from database import SessionLocal, ensure_tables
from models import ClinicUser
from util import now_iso

DEFAULT_ACCOUNTS = (
    ("doctor@clinic.local", "Dr. Ali Fares", "doctor"),
    ("secretary@clinic.local", "Clinic Secretary", "secretary"),
)


def upsert(db, email: str, name: str, role: str, password: str | None, reset: bool = True) -> str | None:
    email = email.strip().lower()
    user = db.query(ClinicUser).filter(ClinicUser.email == email).first()
    if user and not reset:
        return None
    password = password or secrets.token_urlsafe(9)
    if user:
        user.name, user.role, user.active = name or user.name, role, True
        user.password_hash = hash_password(password)
    else:
        db.add(ClinicUser(email=email, name=name, role=role, password_hash=hash_password(password), active=True, createdAt=now_iso()))
    db.commit()
    return password


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--defaults", action="store_true")
    parser.add_argument("--email")
    parser.add_argument("--name", default="")
    parser.add_argument("--role", choices=ROLES)
    parser.add_argument("--password")
    args = parser.parse_args()

    ensure_tables()
    db = SessionLocal()
    try:
        if args.defaults:
            for email, name, role in DEFAULT_ACCOUNTS:
                password = upsert(db, email, name, role, None, reset=False)
                if password:
                    print(f"{role:<10} {email:<26} password: {password}")
                else:
                    print(f"{role:<10} {email:<26} already exists (unchanged)")
            return
        if not args.email or not args.role:
            parser.error("--email and --role are required (or use --defaults)")
        password = upsert(db, args.email, args.name or args.email, args.role, args.password)
        print(f"{args.role:<10} {args.email.lower():<26} password: {password}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
