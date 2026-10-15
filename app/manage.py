"""Staff user management. There are no default passwords: each one is chosen or randomly generated.
  python -m app.manage seed-demo          # 3 demo staff (random passwords printed once) + synthetic submissions
  python -m app.manage create-staff --username jdoe --role nurse
"""
import argparse, getpass, secrets, sys, uuid
from sqlalchemy import select
from . import models
from .database import SessionLocal, init_db
from .schemas import PreRegistrationIn
from .services import registration_service as svc
from .services.ai_assistant import MockAIAssistant, build_summary
from .services.auth import hash_password
from .services.workflow import ROLES

DEMO_USERS = [("demo-clerk", "clerk"), ("demo-nurse", "nurse"), ("demo-charge", "charge_nurse")]
SAMPLES = [
    ("Alex", "Sample", "1985-03-02", "416-555-0101", "manual_entry",
     ["Sore throat", "Throat pain and mild fever", "Three days ago", "Slowly getting worse", "None", "No known allergies", "Nothing else"]),
    ("Jordan", "Example", "1972-11-19", "416-555-0102", "scanned_confirmed",
     ["Twisted ankle", "Swelling and pain when walking", "This morning", "About the same", "None", "None", "Nothing else"]),
    ("Sam", "Placeholder", "2001-07-08", "416-555-0103", "unavailable", ["Headache for two days"]),
]

def seed_demo(db) -> dict:
    passwords = {}
    for username, role in DEMO_USERS:
        if not db.scalar(select(models.StaffUser).where(models.StaffUser.username == username)):
            pw = secrets.token_urlsafe(12)
            db.add(models.StaffUser(username=username, password_hash=hash_password(pw), role=role))
            passwords[username] = pw
    db.commit()
    if not db.scalar(select(models.Submission.id)):
        for first, last, dob, phone, card, answers in SAMPLES:
            data = PreRegistrationIn(legal_first_name=first, legal_last_name=last, date_of_birth=dob, phone=phone,
                                     health_card_status=card, symptom_answers=answers, consent_registration=True,
                                     consent_ai_processing=True, idempotency_key=uuid.uuid4().hex)
            svc.create(db, data, build_summary(answers, MockAIAssistant(), True) if answers else None)
    return passwords

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-demo")
    c = sub.add_parser("create-staff")
    c.add_argument("--username", required=True)
    c.add_argument("--role", required=True, choices=ROLES)
    a = ap.parse_args()
    init_db()
    with SessionLocal() as db:
        if a.cmd == "seed-demo":
            pws = seed_demo(db)
            if not pws:
                print("Demo users already exist. Passwords are never shown again; delete checkin.db to start over.")
            for u, p in pws.items():
                print(f"{u}: {p}")
            if pws:
                print("Save these now. They are shown once and only a hash is stored.")
        else:
            pw = getpass.getpass("Password (12+ characters): ")
            if len(pw) < 12 or pw != getpass.getpass("Repeat password: "):
                sys.exit("Password too short or not matching.")
            db.add(models.StaffUser(username=a.username.strip().lower(), password_hash=hash_password(pw), role=a.role))
            db.commit()
            print("Created.")

if __name__ == "__main__":
    main()
