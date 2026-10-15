import base64, hashlib, secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from .. import models
from ..config import RETENTION_DAYS
from ..schemas import PreRegistrationIn

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def _new_reference(db: Session) -> str:
    while True:  # random, non-sequential
        ref = "DEMO-" + base64.b32encode(secrets.token_bytes(5)).decode()
        if not db.scalar(select(models.Submission.id).where(models.Submission.reference == ref)):
            return ref

def audit(db: Session, event: str, reference: str | None, actor: str = "patient"):
    db.add(models.AuditEvent(event=event, reference=reference, actor=actor))

def create(db: Session, data: PreRegistrationIn, summary=None):
    """Returns (submission, token_or_None, created). Repeat idempotency key returns the original."""
    existing = db.scalar(select(models.Submission).where(models.Submission.idempotency_key == data.idempotency_key))
    if existing:
        return existing, None, False
    token = secrets.token_urlsafe(24)
    sub = models.Submission(
        reference=_new_reference(db), token_hash=_hash(token),
        idempotency_key=data.idempotency_key, health_card_status=data.health_card_status,
        retention_until=datetime.now(timezone.utc) + timedelta(days=RETENTION_DAYS),
        patient=models.Patient(**data.model_dump(include={
            "completing_for", "legal_first_name", "legal_last_name", "preferred_name",
            "date_of_birth", "phone", "email", "accessibility_needs"})),
        summary=(models.Summary(text=summary.text, source=summary.source) if summary else None),
        responses=[models.SymptomResponse(position=i, answer=a) for i, a in enumerate(data.symptom_answers)],
        consents=[models.Consent(kind="registration", granted=True),
                  models.Consent(kind="ai_processing", granted=data.consent_ai_processing)],
    )
    db.add(sub)
    audit(db, "submission_created", sub.reference)
    db.commit()
    return sub, token, True

def get_authorized(db: Session, reference: str, token: str | None):
    sub = db.scalar(select(models.Submission).where(models.Submission.reference == reference))
    if sub and token and secrets.compare_digest(sub.token_hash, _hash(token)):
        return sub
    return None

def received_and_outstanding(sub: models.Submission):
    received = ["Patient details", "Consent choices", "Health card status (no card number or image stored)"]
    if sub.responses:
        received.insert(1, "Symptom answers (patient-reported)")
    outstanding = ["Identity confirmation by staff", "Clinical assessment by hospital staff"]
    outstanding.insert(1, "Health card verification through an authorized hospital process")
    if sub.health_card_status in ("not_provided", "unavailable"):
        outstanding.insert(1, "Health card or insurance details")
    return received, outstanding

def delete_submission(db: Session, sub: models.Submission):
    ref = sub.reference
    db.delete(sub)
    audit(db, "submission_deleted", ref)
    db.commit()

def purge_expired(db: Session) -> int:
    expired = db.scalars(select(models.Submission).where(
        models.Submission.retention_until < datetime.now(timezone.utc).replace(tzinfo=None))).all()
    for s in expired:
        audit(db, "submission_purged_retention", s.reference, actor="system")
        db.delete(s)
    db.commit()
    return len(expired)
