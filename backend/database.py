import os
import threading

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# For now this is the hospital system's database. The clinic only ever creates
# and writes its own `clinic_*` tables (see models.py), so moving it to its own
# database later is: copy those tables, change DATABASE_URL.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 10})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_tables_ready = False
_tables_lock = threading.Lock()


def ensure_tables() -> None:
    """Creates the clinic tables on first use, so the service recovers by
    itself if the database was down when it booted. Base only knows the
    clinic's models, so no hospital table is ever created or altered."""
    global _tables_ready
    if _tables_ready:
        return
    with _tables_lock:
        if not _tables_ready:
            import models  # noqa: F401  (registers the tables on Base)

            Base.metadata.create_all(bind=engine)
            _tables_ready = True


def get_db():
    ensure_tables()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def table_exists(name: str) -> bool:
    try:
        return inspect(engine).has_table(name)
    except SQLAlchemyError:
        return False


def database_is_up() -> bool:
    try:
        ensure_tables()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
