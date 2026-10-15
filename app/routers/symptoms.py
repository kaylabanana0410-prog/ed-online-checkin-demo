from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ..services.ratelimit import limit
from ..dependencies import get_ai_assistant, get_rules_engine
from ..services import symptom_questionnaire as q
from ..services.ai_assistant import DISCLAIMER, build_summary

router = APIRouter(prefix="/api/symptoms", tags=["symptoms"], dependencies=[Depends(limit("symptoms"))])

class AnswersIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)  # no identity fields accepted
    answers: list[str] = Field(default_factory=list, max_length=len(q.QUESTIONS))
    @field_validator("answers")
    @classmethod
    def _len(cls, v):
        if any(len(a) > 500 for a in v):
            raise ValueError("Each answer must be 500 characters or fewer.")
        return v

class SummaryIn(AnswersIn):
    ai_consent: bool = False

@router.get("/questions")
def questions():
    return {"questions": [text for _, text in q.QUESTIONS]}

@router.post("/turn")
def turn(body: AnswersIn, rules=Depends(get_rules_engine)):
    ev = rules.evaluate(body.answers)
    nxt = q.next_question(len(body.answers))
    return {"next_question": nxt, "complete": nxt is None, "emergency": ev.emergency,
            "degraded": ev.degraded, "messages": ev.messages}

@router.post("/summary")
def summary(body: SummaryIn, rules=Depends(get_rules_engine), ai=Depends(get_ai_assistant)):
    ev = rules.evaluate(body.answers)  # always runs, whatever the AI does
    s = build_summary(body.answers, ai, body.ai_consent)
    return {"summary": s.text, "source": s.source, "disclaimer": DISCLAIMER,
            "emergency": ev.emergency, "degraded": ev.degraded, "messages": ev.messages}
