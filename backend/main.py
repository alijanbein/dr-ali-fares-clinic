import os
import sys

# Windows defaults redirected output to cp1252; printing Arabic would raise.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from database import database_is_up  # noqa: E402
from routers.appointments import router as appointments_router  # noqa: E402
from routers.auth import router as auth_router  # noqa: E402
from routers.booking_requests import router as booking_requests_router  # noqa: E402
from routers.dictation import router as dictation_router  # noqa: E402
from routers.documents import router as documents_router  # noqa: E402
from routers.patients import router as patients_router  # noqa: E402
from routers.visits import router as visits_router  # noqa: E402

app = FastAPI(title="Clinic System - Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5190").split(",") if o.strip()],
    # A tablet/phone on the clinic network opening the dev server by LAN IP.
    allow_origin_regex=r"https?://(192\.168|10\.\d+|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+:5190",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
def database_error(_request: Request, exc: SQLAlchemyError):
    # The message can include connection details, so only the type is logged
    # and nothing is sent to the browser.
    print(f"Database error: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
    return JSONResponse(status_code=503, content={"detail": "The database is temporarily unavailable."})


for r in (
    auth_router,
    patients_router,
    appointments_router,
    visits_router,
    dictation_router,
    documents_router,
    booking_requests_router,
):
    app.include_router(r)


@app.get("/health")
def health():
    return {"status": "ok", "database": "up" if database_is_up() else "down"}
