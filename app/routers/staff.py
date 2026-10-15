import hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from .. import config, models
from ..database import get_db
from ..schemas import PatientCorrection
from ..services.auth import DUMMY_HASH, token_hash, verify_password
from ..services.ratelimit import limit
from ..services.registration_service import audit
from ..services.workflow import PERMS, STEPS, step_view

router = APIRouter(prefix="/api/staff", tags=["staff"])
COOKIE = "staff_session"

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _session(request: Request, db: Session):
    token = request.cookies.get(COOKIE)
    s = db.scalar(select(models.StaffSession).where(models.StaffSession.token_hash == token_hash(token))) if token else None
    user = db.get(models.StaffUser, s.user_id) if s else None
    if not s or s.expires_at < _utcnow() or not user or not user.active:
        raise HTTPException(401, "Sign in required.")
    return user, s

def staff_for(permission: str):
    def dep(request: Request, db: Session = Depends(get_db), x_csrf_token: str | None = Header(None)):
        user, s = _session(request, db)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not x_csrf_token or not hmac.compare_digest(x_csrf_token, s.csrf_token):
                raise HTTPException(403, "Invalid request token.")
        if user.role not in PERMS[permission]:
            raise HTTPException(403, "Your role cannot do this.")
        return user
    return dep

class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(max_length=50)
    password: str = Field(max_length=200)

@router.post("/login", dependencies=[Depends(limit("login"))])
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    key = hashlib.sha256(body.username.strip().lower().encode()).hexdigest()  # attempted names kept only as hashes
    cutoff = _utcnow() - timedelta(minutes=config.LOCKOUT_MINUTES)
    recent = db.scalar(select(func.count()).select_from(models.LoginAttempt).where(
        models.LoginAttempt.key_hash == key, models.LoginAttempt.created_at > cutoff))
    if recent >= config.LOCKOUT_ATTEMPTS:
        audit(db, "staff_login_locked", None, "unknown")
        db.commit()
        raise HTTPException(429, "Too many failed attempts. Please wait and try again later.")
    user = db.scalar(select(models.StaffUser).where(models.StaffUser.username == body.username.strip().lower(),
                                                    models.StaffUser.active.is_(True)))
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not (user and ok):
        db.add(models.LoginAttempt(key_hash=key))
        audit(db, "staff_login_failed", None, "unknown")  # attempted usernames are not recorded
        db.commit()
        raise HTTPException(401, "Incorrect username or password.")
    db.execute(delete(models.LoginAttempt).where(models.LoginAttempt.key_hash == key))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(models.StaffSession(token_hash=token_hash(token), csrf_token=csrf, user_id=user.id,
                               expires_at=_utcnow() + timedelta(hours=config.SESSION_HOURS)))
    audit(db, "staff_login", None, user.username)
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=config.COOKIE_SECURE,
                        max_age=config.SESSION_HOURS * 3600)
    response.headers["Cache-Control"] = "no-store"
    return {"username": user.username, "role": user.role, "csrf_token": csrf}

@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    user, s = _session(request, db)
    return {"username": user.username, "role": user.role, "csrf_token": s.csrf_token}

@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db), user=Depends(staff_for("view"))):
    _, s = _session(request, db)
    db.delete(s)
    audit(db, "staff_logout", None, user.username)
    db.commit()
    response.delete_cookie(COOKIE)
    return {"ok": True}

@router.get("/destinations")
def destinations(user=Depends(staff_for("view"))):
    return {"destinations": config.DESTINATIONS}

def _missing(sub):
    m = []
    if not sub.responses:
        m.append("symptom answers")
    if sub.health_card_status in ("not_provided", "unavailable"):
        m.append("health card details")
    return m

@router.get("/submissions")
def list_submissions(q: str | None = None, user=Depends(staff_for("view")), db: Session = Depends(get_db)):
    stmt = select(models.Submission).order_by(models.Submission.created_at.desc()).limit(100)
    if q and q.strip():
        stmt = stmt.where(models.Submission.reference.contains(q.strip().upper()[:20], autoescape=True))
    out = []
    for s in db.scalars(stmt):  # no names in the list view
        sv = step_view(s)
        admin = [x for x in sv if x["kind"] == "administrative"]
        out.append({"reference": s.reference, "submitted_at": s.created_at.isoformat() + "Z",
                    "health_card_status": s.health_card_status, "missing": _missing(s),
                    "admin_done": sum(x["completed"] for x in admin), "admin_total": len(admin),
                    "clinical_assessment_complete": next(x["completed"] for x in sv if x["step"] == "clinical_assessment_complete"),
                    "destination": bool(s.destination)})
    return out

def _get(db: Session, reference: str):
    s = db.scalar(select(models.Submission).where(models.Submission.reference == reference))
    if not s:
        raise HTTPException(404, "Not found.")
    return s

@router.get("/submissions/{reference}")
def detail(reference: str, user=Depends(staff_for("view")), db: Session = Depends(get_db)):
    s = _get(db, reference)
    audit(db, "record_viewed", s.reference, user.username)
    db.commit()
    p, d = s.patient, s.destination
    steps = [dict(x, at=x["at"].isoformat() + "Z" if x["at"] else None, can_edit=user.role in PERMS[x["kind"]])
             for x in step_view(s)]
    log = db.scalars(select(models.AuditEvent).where(models.AuditEvent.reference == s.reference)
                     .order_by(models.AuditEvent.id)).all()
    return {
        "reference": s.reference, "submitted_at": s.created_at.isoformat() + "Z", "completing_for": p.completing_for,
        "patient": {"legal_first_name": p.legal_first_name, "legal_last_name": p.legal_last_name,
                    "preferred_name": p.preferred_name, "date_of_birth": p.date_of_birth.isoformat(),
                    "phone": p.phone, "email": p.email, "accessibility_needs": p.accessibility_needs},
        "symptom_answers": [r.answer for r in sorted(s.responses, key=lambda r: r.position)],
        "summary": {"text": s.summary.text, "source": s.summary.source} if s.summary else None,
        "consents": {c.kind: c.granted for c in s.consents}, "health_card_status": s.health_card_status,
        "missing": _missing(s), "steps": steps,
        "destination": {"destination": d.destination, "instructions": d.instructions, "authorized_by": d.authorized_by} if d else None,
        "can_set_destination": user.role in PERMS["destination"], "can_edit_patient": user.role in PERMS["edit_patient"],
        "audit": [{"event": e.event, "actor": e.actor, "at": e.created_at.isoformat() + "Z"} for e in log],
    }

class StepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed: bool

@router.put("/submissions/{reference}/steps/{step}")
def set_step(reference: str, step: str, body: StepIn, user=Depends(staff_for("view")), db: Session = Depends(get_db)):
    if step not in STEPS:
        raise HTTPException(404, "Unknown step.")
    if user.role not in PERMS[STEPS[step][0]]:
        raise HTTPException(403, "Your role cannot do this.")
    s = _get(db, reference)
    row = next((x for x in s.steps if x.step == step), None)
    if not row:
        row = models.WorkflowStep(step=step)
        s.steps.append(row)
    row.completed, row.completed_by, row.updated_at = body.completed, user.username, _utcnow()
    audit(db, f"step_{step}_{'completed' if body.completed else 'reopened'}", s.reference, user.username)
    db.commit()
    return {"ok": True}

class DestinationIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    destination: str | None = Field(None, max_length=100)
    instructions: str | None = Field(None, max_length=300)

@router.put("/submissions/{reference}/destination")
def set_destination(reference: str, body: DestinationIn, user=Depends(staff_for("destination")), db: Session = Depends(get_db)):
    s = _get(db, reference)
    if body.destination and body.destination not in config.DESTINATIONS:
        raise HTTPException(422, "Choose one of the approved destinations.")
    if s.destination:
        s.destination = None  # replaced below, or cleared
        db.flush()
    if body.destination:
        s.destination = models.Destination(destination=body.destination, instructions=body.instructions or None,
                                           authorized_by=user.username)
    audit(db, "destination_set" if body.destination else "destination_cleared", s.reference, user.username)
    db.commit()
    return {"ok": True}

@router.patch("/submissions/{reference}/patient")
def correct_patient(reference: str, body: PatientCorrection, user=Depends(staff_for("edit_patient")), db: Session = Depends(get_db)):
    s = _get(db, reference)
    for f in body.model_fields_set:  # audit records field names only, never values
        setattr(s.patient, f, getattr(body, f))
        audit(db, f"admin_correction_{f}", s.reference, user.username)
    db.commit()
    return {"ok": True}
