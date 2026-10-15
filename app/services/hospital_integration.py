"""Boundary to the hospital's clinical workflow. By design, nothing here can carry a priority,
CTAS score, or 'assessment complete' flag: only the authorized hospital system does that."""
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class WorkflowReceipt:
    status: str          # only ever "pending_staff_review" from this prototype
    simulated: bool = True

class ClinicalWorkflowClient(Protocol):
    def submit_for_review(self, reference: str, summary: str | None) -> WorkflowReceipt: ...

class MockClinicalWorkflow:
    """SIMULATED stand-in. Real integration needs hospital credentials and clinical validation."""
    def submit_for_review(self, reference: str, summary: str | None) -> WorkflowReceipt:
        return WorkflowReceipt(status="pending_staff_review")

@dataclass(frozen=True)
class CardValidationResult:
    format_valid: bool
    eligibility: str = "not_checked"  # eligibility is only ever checked by hospital staff via authorized systems
    simulated: bool = True

class CardValidationClient(Protocol):
    def check_format(self, number: str, version_code: str | None) -> CardValidationResult: ...

class MockCardValidation:
    """SIMULATED. Checks format only. Never confirms eligibility or registration."""
    def check_format(self, number: str, version_code: str | None) -> CardValidationResult:
        ok = len(number) == 10 and number.isdigit() and (not version_code or (len(version_code) == 2 and version_code.isalpha()))
        return CardValidationResult(format_valid=ok)
