"""Stage 2 tables. Health card numbers and images are never stored, only a status.
Admin verification, clinical workflow and destination tables arrive in Stage 5."""
from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def now() -> datetime:
    return datetime.now(timezone.utc)

class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    completing_for: Mapped[str] = mapped_column(String(10))
    legal_first_name: Mapped[str] = mapped_column(String(80))
    legal_last_name: Mapped[str] = mapped_column(String(80))
    preferred_name: Mapped[str | None] = mapped_column(String(80))
    date_of_birth: Mapped[date] = mapped_column(Date)
    phone: Mapped[str] = mapped_column(String(10))
    email: Mapped[str | None] = mapped_column(String(254))
    accessibility_needs: Mapped[str | None] = mapped_column(String(300))

class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="submitted")
    health_card_status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    retention_until: Mapped[datetime] = mapped_column(DateTime)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    patient: Mapped[Patient] = relationship(cascade="all, delete-orphan", single_parent=True)
    responses: Mapped[list["SymptomResponse"]] = relationship(cascade="all, delete-orphan")
    consents: Mapped[list["Consent"]] = relationship(cascade="all, delete-orphan")
    summary: Mapped["Summary"] = relationship(uselist=False, cascade="all, delete-orphan")
    steps: Mapped[list["WorkflowStep"]] = relationship(cascade="all, delete-orphan")
    destination: Mapped["Destination"] = relationship(uselist=False, cascade="all, delete-orphan")

class SymptomResponse(Base):
    __tablename__ = "symptom_responses"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    position: Mapped[int]
    answer: Mapped[str] = mapped_column(Text)  # patient-reported, not verified

class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    kind: Mapped[str] = mapped_column(String(30))  # registration | ai_processing
    granted: Mapped[bool] = mapped_column(Boolean)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class AuditEvent(Base):
    """No names or health data: event type and reference only. Survives submission deletion."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event: Mapped[str] = mapped_column(String(50))
    reference: Mapped[str | None] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(30), default="patient")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Summary(Base):
    """AI-generated when source == "ai"; otherwise just the patient's own answers laid out."""
    __tablename__ = "summaries"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), unique=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(10))  # ai | fallback
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class WorkflowStep(Base):
    """Staff-completed administrative and clinical steps. A missing row means pending."""
    __tablename__ = "workflow_steps"
    __table_args__ = (UniqueConstraint("submission_id", "step"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    step: Mapped[str] = mapped_column(String(40))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_by: Mapped[str | None] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Destination(Base):
    __tablename__ = "destinations"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), unique=True)
    destination: Mapped[str] = mapped_column(String(100))
    instructions: Mapped[str | None] = mapped_column(String(300))
    authorized_by: Mapped[str] = mapped_column(String(50))
    authorized_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class StaffUser(Base):
    __tablename__ = "staff_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class StaffSession(Base):
    __tablename__ = "staff_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey("staff_users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class LoginAttempt(Base):
    """Failed staff logins, keyed by a hash of the username so attempted names are never stored."""
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
