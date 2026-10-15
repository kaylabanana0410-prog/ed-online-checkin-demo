"""Interchangeable AI summarizer. The mock is deterministic and runs locally (no data leaves the app).
The AI only summarizes what the patient reported. It never assesses urgency, diagnoses, or scores."""
import logging, re
from dataclasses import dataclass
from typing import Protocol
from .symptom_questionnaire import labelled

log = logging.getLogger("ai")
DISCLAIMER = "Preliminary summary of what was reported. It is not a diagnosis and does not assess urgency."
_FORBIDDEN = re.compile(r"\byou (have|likely have|probably have)\b|\bdiagnosis (is|:)|safe to wait|\bctas\b|triage (level|score)", re.I)

class AIUnavailable(Exception):
    pass

@dataclass
class AISummary:
    text: str
    confidence: float

class AIAssistant(Protocol):
    def summarize(self, answers: list[str]) -> AISummary: ...

class MockAIAssistant:
    """SIMULATED. Receives symptom answers only: never name, birth date, phone or health card data."""
    def __init__(self, mode: str = "normal"):
        self.mode = mode
    def summarize(self, answers: list[str]) -> AISummary:
        if self.mode == "unavailable":
            raise AIUnavailable()
        conf = 0.2 if self.mode == "uncertain" else (0.9 if sum(map(len, answers)) >= 40 else 0.3)
        return AISummary(labelled(answers), conf)

@dataclass
class SummaryResult:
    text: str
    source: str  # "ai" or "fallback"

def build_summary(answers: list[str], ai: AIAssistant, ai_consent: bool, min_confidence: float = 0.6) -> SummaryResult:
    if ai_consent:  # AI is only used with the patient's separate, optional consent
        try:
            r = ai.summarize(answers)
            if r.confidence >= min_confidence and not _FORBIDDEN.search(r.text):
                return SummaryResult(r.text, "ai")
        except Exception as e:  # any AI failure falls back; never log answers
            log.warning("ai_summary_failed: %s", type(e).__name__)
    return SummaryResult(labelled(answers) or "No symptom answers provided.", "fallback")
