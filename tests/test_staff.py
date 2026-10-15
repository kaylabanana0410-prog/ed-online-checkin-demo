import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import manage, models
from app.database import Base, get_db
from app.main import app
from app.services.auth import hash_password, verify_password

PW = "correct-horse-battery"
LONG = ["Sore throat for three days", "Throat pain and mild fever", "Three days ago", "Getting worse slowly"]

class World:
    pass

@pytest.fixture
def world():
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
    w = World()
    w.Session = Session
    patient_client = TestClient(app)
    def submit(**kw):
        p = dict(legal_first_name="Test", legal_last_name="Patient", date_of_birth="1990-05-17", phone="416-555-0123",
                 consent_registration=True, symptom_answers=LONG, idempotency_key=uuid.uuid4().hex)
        p.update(kw)
        r = patient_client.post("/api/preregistrations", json=p)
        assert r.status_code == 201
        return r.json()
    def staff(role):
        name = f"{role}-{uuid.uuid4().hex[:6]}"
        with Session() as db:
            db.add(models.StaffUser(username=name, password_hash=hash_password(PW), role=role))
            db.commit()
        c = TestClient(app)
        r = c.post("/api/staff/login", json={"username": name, "password": PW})
        assert r.status_code == 200
        return c, {"X-CSRF-Token": r.json()["csrf_token"]}
    w.submit, w.staff = submit, staff
    yield w
    app.dependency_overrides.clear()

def step(c, h, ref, name, done=True):
    return c.put(f"/api/staff/submissions/{ref}/steps/{name}", json={"completed": done}, headers=h)

def dest(c, h, ref, value, ins=None):
    return c.put(f"/api/staff/submissions/{ref}/destination", json={"destination": value, "instructions": ins}, headers=h)

def test_requires_login(world):
    ref = world.submit()["reference"]
    c = TestClient(app)
    assert c.get("/api/staff/submissions").status_code == 401
    assert c.get(f"/api/staff/submissions/{ref}").status_code == 401

def test_failed_logins_are_generic(world):
    world.staff("clerk")
    c = TestClient(app)
    a = c.post("/api/staff/login", json={"username": "nobody", "password": PW})
    b = c.post("/api/staff/login", json={"username": "clerk-x", "password": "wrong"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()

def test_passwords_hashed_and_cookie_flags(world):
    c = TestClient(app)
    name = "clerk-h"
    with world.Session() as db:
        db.add(models.StaffUser(username=name, password_hash=hash_password(PW), role="clerk")); db.commit()
    r = c.post("/api/staff/login", json={"username": name, "password": PW})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    with world.Session() as db:
        h = db.query(models.StaffUser).one().password_hash
    assert h.startswith("scrypt$") and PW not in h and verify_password(PW, h)

def test_logout_and_expiry_end_session(world):
    c, h = world.staff("clerk")
    assert c.get("/api/staff/me").status_code == 200
    c.post("/api/staff/logout", headers=h)
    assert c.get("/api/staff/submissions").status_code == 401
    c2, _ = world.staff("clerk")
    with world.Session() as db:
        db.query(models.StaffSession).update({"expires_at": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)}); db.commit()
    assert c2.get("/api/staff/submissions").status_code == 401

def test_csrf_token_required_for_changes(world):
    ref = world.submit()["reference"]
    c, h = world.staff("clerk")
    assert step(c, {}, ref, "identity_confirmed").status_code == 403
    assert step(c, {"X-CSRF-Token": "wrong"}, ref, "identity_confirmed").status_code == 403
    assert step(c, h, ref, "identity_confirmed").status_code == 200

def test_role_permissions(world):
    ref = world.submit()["reference"]
    clerk, ch = world.staff("clerk")
    nurse, nh = world.staff("nurse")
    charge, gh = world.staff("charge_nurse")
    assert step(clerk, ch, ref, "identity_confirmed").status_code == 200
    assert step(clerk, ch, ref, "clinical_assessment_complete").status_code == 403
    assert dest(clerk, ch, ref, "Main waiting area (demo placeholder)").status_code == 403
    assert step(nurse, nh, ref, "clinical_assessment_complete").status_code == 200
    assert step(nurse, nh, ref, "wristband_issued").status_code == 403
    assert dest(nurse, nh, ref, "Main waiting area (demo placeholder)").status_code == 200
    assert step(charge, gh, ref, "wristband_issued").status_code == 200
    assert step(charge, gh, ref, "summary_reviewed").status_code == 200
    assert step(clerk, ch, ref, "no_such_step").status_code == 404

def test_nothing_is_complete_after_submission(world):
    ref = world.submit()["reference"]
    c, _ = world.staff("nurse")
    d = c.get(f"/api/staff/submissions/{ref}").json()
    assert not any(s["completed"] for s in d["steps"]) and d["destination"] is None

def test_destination_must_be_approved_and_can_clear(world):
    ref = world.submit()["reference"]
    c, h = world.staff("nurse")
    assert dest(c, h, ref, "Zone Made Up").status_code == 422
    assert dest(c, h, ref, "Main waiting area (demo placeholder)", "Sit near the desk").status_code == 200
    assert c.get(f"/api/staff/submissions/{ref}").json()["destination"]["authorized_by"].startswith("nurse")
    assert dest(c, h, ref, None).status_code == 200
    assert c.get(f"/api/staff/submissions/{ref}").json()["destination"] is None

def test_patient_sees_destination_only_after_authorization(world):
    j = world.submit()
    url, th = f"/api/preregistrations/{j['reference']}", {"X-Access-Token": j["access_token"]}
    pc = TestClient(app)
    first = pc.get(url, headers=th).json()
    assert first["destination"] is None and len(first["steps"]) == 6 and not any(s["completed"] for s in first["steps"])
    c, h = world.staff("nurse")
    dest(c, h, j["reference"], "Main waiting area (demo placeholder)")
    after = pc.get(url, headers=th).json()
    assert after["destination"] == "Main waiting area (demo placeholder)"
    assert not {"priority", "ctas", "triage"} & set(after)

def test_patient_token_cannot_change_staff_state(world):
    j = world.submit()
    r = TestClient(app).put(f"/api/staff/submissions/{j['reference']}/steps/clinical_assessment_complete",
                            json={"completed": True}, headers={"X-Access-Token": j["access_token"]})
    assert r.status_code == 401

def test_action_log_records_staff_and_stays_phi_free(world):
    ref = world.submit()["reference"]
    c, h = world.staff("clerk")
    step(c, h, ref, "identity_confirmed")
    c.patch(f"/api/staff/submissions/{ref}/patient", json={"phone": "416-555-0199"}, headers=h)
    log = c.get(f"/api/staff/submissions/{ref}").json()["audit"]
    events = {e["event"] for e in log}
    assert {"step_identity_confirmed_completed", "admin_correction_phone", "record_viewed", "submission_created"} <= events
    text = str(log)
    assert all(x not in text for x in ("4165550123", "4165550199", "Test", "Patient")) and any(e["actor"].startswith("clerk") for e in log)

def test_search_by_reference_without_names(world):
    ref = world.submit()["reference"]
    world.submit()
    c, _ = world.staff("nurse")
    r = c.get("/api/staff/submissions", params={"q": ref[5:9].lower()})
    assert ref in [x["reference"] for x in r.json()] and "Patient" not in r.text
    assert c.get("/api/staff/submissions", params={"q": "ZZZZZZ"}).json() == []
    assert len(c.get("/api/staff/submissions").json()) == 2

def test_admin_correction_rules(world):
    ref = world.submit()["reference"]
    clerk, ch = world.staff("clerk")
    nurse, nh = world.staff("nurse")
    url = f"/api/staff/submissions/{ref}/patient"
    assert clerk.patch(url, json={"phone": "416-555-0188"}, headers=ch).status_code == 200
    assert clerk.get(f"/api/staff/submissions/{ref}").json()["patient"]["phone"] == "4165550188"
    assert clerk.patch(url, json={"phone": "123"}, headers=ch).status_code == 422
    assert clerk.patch(url, json={"phone": None}, headers=ch).status_code == 422
    assert clerk.patch(url, json={}, headers=ch).status_code == 422
    assert nurse.patch(url, json={"phone": "416-555-0188"}, headers=nh).status_code == 403

def test_summary_is_labelled_by_source(world):
    c, _ = world.staff("nurse")
    a = world.submit(consent_ai_processing=True)["reference"]
    b = world.submit(consent_ai_processing=False)["reference"]
    assert c.get(f"/api/staff/submissions/{a}").json()["summary"]["source"] == "ai"
    assert c.get(f"/api/staff/submissions/{b}").json()["summary"]["source"] == "fallback"

def test_patient_deletion_removes_staff_data(world):
    j = world.submit()
    c, h = world.staff("charge_nurse")
    step(c, h, j["reference"], "identity_confirmed"); dest(c, h, j["reference"], "Main waiting area (demo placeholder)")
    assert TestClient(app).delete(f"/api/preregistrations/{j['reference']}", headers={"X-Access-Token": j["access_token"]}).status_code == 204
    with world.Session() as db:
        assert all(db.query(m).count() == 0 for m in (models.WorkflowStep, models.Destination, models.Summary, models.Patient))

def test_seed_demo_has_unique_random_passwords(world):
    with world.Session() as db:
        pws = manage.seed_demo(db)
        assert len(pws) == 3 and len(set(pws.values())) == 3
        assert db.query(models.Submission).count() == 3
        for u in db.query(models.StaffUser):
            assert verify_password(pws[u.username], u.password_hash) and pws[u.username] not in u.password_hash
        assert manage.seed_demo(db) == {}
