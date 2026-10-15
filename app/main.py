import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import config
from .database import SessionLocal, init_db
from .routers import documents, registration, staff, symptoms
from .services.auth import purge_security_tables
from .services.registration_service import purge_expired

STATIC = Path(__file__).parent / "static"
log = logging.getLogger("app")

# No inline scripts allowed. Bootstrap CSS comes from a CDN here; self-host it in production.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' https://cdn.jsdelivr.net; "
       "style-src-attr 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; "
       "font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")

def secure(response, path: str):
    h = response.headers
    h["Content-Security-Policy"] = CSP
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    if path.startswith("/api/") or path in ("/", "/staff"):
        h["Cache-Control"] = "no-store"
    if config.COOKIE_SECURE:  # only meaningful over HTTPS
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        purge_expired(db)
        purge_security_tables(db)
    yield

app = FastAPI(title="ED Online Check-In (demo, synthetic data)", lifespan=lifespan, redoc_url=None,
              docs_url="/docs" if config.DEBUG_DOCS else None,
              openapi_url="/openapi.json" if config.DEBUG_DOCS else None)

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    early = None
    if request.method == "POST" and request.url.path == "/api/documents/card-scan":
        try:  # reject obviously oversize uploads from the header alone (proxies should also cap this)
            size = int(request.headers.get("content-length", "0"))
        except ValueError:
            size = 0
        if size > config.MAX_UPLOAD_BYTES + 100_000:
            early = JSONResponse({"detail": "That file is too large."}, status_code=413)
    return secure(early or await call_next(request), request.url.path)

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # Field names and messages only: never echo submitted values back or into logs.
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"].removeprefix("Value error, ")}
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={"errors": errors})

@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.error("unhandled_error: %s", type(exc).__name__)  # class name only: messages can contain personal data
    return secure(JSONResponse({"detail": "Something went wrong. Please try again, or ask staff for help."},
                               status_code=500), request.url.path)

app.include_router(registration.router)
app.include_router(symptoms.router)
app.include_router(documents.router)
app.include_router(staff.router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.get("/staff", include_in_schema=False)
def staff_page():
    return FileResponse(STATIC / "staff.html")

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")
