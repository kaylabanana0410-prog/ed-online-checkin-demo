import re
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

def check_dob(v: date):
    if v > date.today() or v.year < 1900:
        raise ValueError("Enter a valid date of birth that is not in the future.")
    return v

def clean_phone(v: str):
    d = re.sub(r"\D", "", v)
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) != 10:
        raise ValueError("Enter a 10-digit phone number.")
    return d

def clean_email(v: str | None):
    if not v:
        return None
    if len(v) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
        raise ValueError("Check the email format or leave it blank.")
    return v

class PreRegistrationIn(BaseModel):
    # extra="forbid": unexpected fields (e.g. a health card number) are rejected, not stored.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    completing_for: Literal["self", "other"] = "self"
    legal_first_name: str = Field(min_length=1, max_length=80)
    legal_last_name: str = Field(min_length=1, max_length=80)
    preferred_name: str | None = Field(None, max_length=80)
    date_of_birth: date
    phone: str
    email: str | None = None
    accessibility_needs: str | None = Field(None, max_length=300)
    symptom_answers: list[str] = Field(default_factory=list, max_length=10)
    health_card_status: Literal["not_provided", "scanned_unconfirmed", "scanned_confirmed", "manual_entry", "unavailable"] = "not_provided"
    consent_registration: bool
    consent_ai_processing: bool = False
    idempotency_key: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date):
        return check_dob(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str):
        return clean_phone(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None):
        return clean_email(v)

    @field_validator("symptom_answers")
    @classmethod
    def _answers(cls, v: list[str]):
        if any(len(a) > 500 for a in v):
            raise ValueError("Each symptom answer must be 500 characters or fewer.")
        return [a.strip() for a in v if a.strip()]

    @field_validator("consent_registration")
    @classmethod
    def _consent(cls, v: bool):
        if not v:
            raise ValueError("Required consent is needed to submit.")
        return v

class PreRegistrationOut(BaseModel):
    reference: str
    access_token: str | None = None  # shown once; only a hash is stored
    submitted_at: datetime
    received: list[str]
    outstanding: list[str]
    notice: str = ("Online pre-registration only. Not completed hospital registration, "
                   "a queue position, or a triage assessment.")

class StatusOut(BaseModel):
    reference: str
    status: str
    submitted_at: datetime
    received: list[str]
    outstanding: list[str]
    destination: str | None = None
    destination_instructions: str | None = None
    steps: list[dict] = []

class PatientCorrection(BaseModel):
    """Staff correction of administrative details. Only the fields sent are changed."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    legal_first_name: str | None = Field(None, min_length=1, max_length=80)
    legal_last_name: str | None = Field(None, min_length=1, max_length=80)
    preferred_name: str | None = Field(None, max_length=80)
    date_of_birth: date | None = None
    phone: str | None = None
    email: str | None = None
    accessibility_needs: str | None = Field(None, max_length=300)

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v):
        return check_dob(v) if v else v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return clean_phone(v) if v is not None else v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return clean_email(v)

    @model_validator(mode="after")
    def _check(self):
        if not self.model_fields_set:
            raise ValueError("Send at least one field to correct.")
        for f in ("legal_first_name", "legal_last_name", "date_of_birth", "phone"):
            if f in self.model_fields_set and getattr(self, f) is None:
                raise ValueError(f"{f} cannot be cleared.")
        return self
