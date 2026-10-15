"""Whole journey over the real HTTP API with synthetic data: first visit to destination screen."""
import logging
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import models
from app.database import Base, get_db
from app.main import app
from app.services.auth import hash_password

PW = "correct-horse-battery"
ANSWERS = ["Ankle injury", "Swollen and sore when I walk", "This morning", "About the same", "None", "No known allergies", "Nothing else"]
JPG = b"\xff\xd8\xff\xe0" + b"0" * 200

@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override
    def staff(role):
        name = f"{role}-{uuid.uuid4().hex[:6]}"
        with Session() as db:
            db.add(models.StaffUser(username=name, password_hash=hash_password(PW), role=role)); db.commit()
        c = TestClient(app)
        r = c.post("/api/staff/login", json={"username": name, "password": PW})
        assert r.status_code == 200
        return c, {"X-CSRF-Token": r.json()["csrf_token"]}
    yield staff
    app.dependency_overrides.clear()

def payload(answers, **kw):
    p = dict(legal_first_name="Zelda", legal_last_name="Quartz", date_of_birth="1988-02-29", phone="416-555-0177",
             email=None, symptom_answers=answers, health_card_status="scanned_confirmed", consent_registration=True,
             consent_ai_processing=True, idempotency_key=uuid.uuid4().hex)
    p.update(kw)
    return p

def test_full_journey_first_visit_to_destination(env, caplog):
    caplog.set_level(logging.DEBUG)
    pc = TestClient(app)
    # Step 1: welcome page shows the title and the 911 notice
    home = pc.get("/")
    assert home.status_code == 200 and "Emergency Department Online Check-In" in home.text and "call 911" in home.text
    # Step 3: guided questions, no warning for a minor injury
    questions = pc.get("/api/symptoms/questions").json()["questions"]
    for i in range(len(questions)):
        t = pc.post("/api/symptoms/turn", json={"answers": ANSWERS[: i + 1]}).json()
        assert not t["emergency"] and t["complete"] == (i == len(questions) - 1)
    # Step 4: card image read once, fields unverified, format check simulated
    scan = pc.post("/api/documents/card-scan", files={"file": ("c.jpg", JPG, "image/jpeg")}).json()
    assert scan["fields"] and all(not f["verified"] for f in scan["fields"])
    number = next(f["value"] for f in scan["fields"] if f["name"] == "health_number")
    val = pc.post("/api/documents/card-validate", json={"health_number": number}).json()
    assert val["simulated"] and val["eligibility"] == "not_checked" and number not in val["masked_number"]
    # Step 5: summary preview, then submit
    s = pc.post("/api/symptoms/summary", json={"answers": ANSWERS, "ai_consent": True}).json()
    assert s["source"] == "ai" and "not a diagnosis" in s["disclaimer"]
    sub = pc.post("/api/preregistrations", json=payload(ANSWERS))
    assert sub.status_code == 201
    j = sub.json()
    ref, th = j["reference"], {"X-Access-Token": j["access_token"]}
    # Step 6-7: confirmation is pre-registration only; nothing is done yet
    assert "not completed hospital registration" in j["notice"].lower()
    before = pc.get(f"/api/preregistrations/{ref}", headers=th).json()
    assert before["destination"] is None and not any(x["completed"] for x in before["steps"])
    # Staff side: clerk, nurse, charge nurse each do only their part
    clerk, ch = env("clerk"); nurse, nh = env("nurse"); charge, gh = env("charge_nurse")
    assert ref in [r["reference"] for r in clerk.get("/api/staff/submissions", params={"q": ref[6:10]}).json()]
    d = clerk.get(f"/api/staff/submissions/{ref}").json()
    assert d["patient"]["legal_last_name"] == "Quartz" and d["summary"]["source"] == "ai" and number not in str(d)
    put = lambda c, h, step: c.put(f"/api/staff/submissions/{ref}/steps/{step}", json={"completed": True}, headers=h)
    assert put(clerk, ch, "identity_confirmed").status_code == 200
    assert clerk.patch(f"/api/staff/submissions/{ref}/patient", json={"phone": "416-555-0178"}, headers=ch).status_code == 200
    assert put(clerk, ch, "clinical_assessment_complete").status_code == 403
    assert put(nurse, nh, "summary_reviewed").status_code == 200 and put(nurse, nh, "clinical_assessment_complete").status_code == 200
    assert put(charge, gh, "wristband_issued").status_code == 200
    r = nurse.put(f"/api/staff/submissions/{ref}/destination", headers=nh,
                  json={"destination": "Main waiting area (demo placeholder)", "instructions": "Check in at the desk"})
    assert r.status_code == 200
    # Step 8: patient sees staff progress and the authorized destination
    after = pc.get(f"/api/preregistrations/{ref}", headers=th).json()
    done = {x["label"] for x in after["steps"] if x["completed"]}
    assert "Identity confirmed by staff" in done and "Clinical assessment completed by authorized staff" in done
    assert after["destination"] == "Main waiting area (demo placeholder)" and after["destination_instructions"] == "Check in at the desk"
    log = nurse.get(f"/api/staff/submissions/{ref}").json()["audit"]
    assert {"step_identity_confirmed_completed", "destination_set", "admin_correction_phone"} <= {e["event"] for e in log}
    # Patient deletion removes it for staff too
    assert pc.delete(f"/api/preregistrations/{ref}", headers=th).status_code == 204
    assert nurse.get(f"/api/staff/submissions/{ref}").status_code == 404
    # No personal data anywhere in application logs
    assert not any(x in caplog.text for x in ("Zelda", "Quartz", "4165550177", "4165550178", number))

def test_warning_never_blocks_submission_or_triages(env):
    pc = TestClient(app)
    answers = ["I have chest pain"] + ANSWERS[1:]
    t = pc.post("/api/symptoms/turn", json={"answers": answers[:1]}).json()
    assert t["emergency"] and "911" in t["messages"][0]
    sub = pc.post("/api/preregistrations", json=payload(answers, health_card_status="unavailable", consent_ai_processing=False))
    assert sub.status_code == 201  # a warning never stops the form or demands more steps
    j = sub.json()
    nurse, _ = env("nurse")
    d = nurse.get(f"/api/staff/submissions/{j['reference']}").json()
    assert not any(s["completed"] for s in d["steps"]) and d["destination"] is None
    status = pc.get(f"/api/preregistrations/{j['reference']}", headers={"X-Access-Token": j["access_token"]}).json()
    assert not {"priority", "ctas", "triage", "zone"} & set(status)
