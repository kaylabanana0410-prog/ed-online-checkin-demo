from datetime import timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.ratelimit import limit
from ..dependencies import get_ai_assistant
from ..services.ai_assistant import build_summary
from ..services.workflow import step_view
from ..schemas import PreRegistrationIn, PreRegistrationOut, StatusOut
from ..services import registration_service as svc

router = APIRouter(prefix="/api/preregistrations", tags=["pre-registration"])

def _utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

@router.post("", response_model=PreRegistrationOut, status_code=201, dependencies=[Depends(limit("submit"))])
def submit(data: PreRegistrationIn, response: Response, db: Session = Depends(get_db), ai=Depends(get_ai_assistant)):
    summary = build_summary(data.symptom_answers, ai, data.consent_ai_processing) if data.symptom_answers else None
    sub, token, created = svc.create(db, data, summary)
    if not created:
        response.status_code = 200  # duplicate submission: same reference, no new token
    rec, out = svc.received_and_outstanding(sub)
    return PreRegistrationOut(reference=sub.reference, access_token=token,
                              submitted_at=_utc(sub.created_at), received=rec, outstanding=out)

def _authorized(reference: str, x_access_token: str | None = Header(None), db: Session = Depends(get_db)):
    if not x_access_token:
        raise HTTPException(401, "Access token required.")
    sub = svc.get_authorized(db, reference, x_access_token)
    if not sub:
        raise HTTPException(404, "Not found.")  # same answer for wrong token or unknown reference
    return sub

@router.get("/{reference}", response_model=StatusOut)
def status(sub=Depends(_authorized)):
    rec, out = svc.received_and_outstanding(sub)
    d = sub.destination
    return StatusOut(reference=sub.reference, status=sub.status, submitted_at=_utc(sub.created_at),
                     received=rec, outstanding=out, destination=d.destination if d else None,
                     destination_instructions=d.instructions if d else None,
                     steps=[{"label": x["label"], "completed": x["completed"]} for x in step_view(sub)])

@router.delete("/{reference}", status_code=204)
def delete(sub=Depends(_authorized), db: Session = Depends(get_db)):
    svc.delete_submission(db, sub)
