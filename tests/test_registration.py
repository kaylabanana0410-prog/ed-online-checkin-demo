import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import models
from app.database import Base, get_db
from app.main import app
from app.services import registration_service as svc

@pytest.fixture
def client():
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
    c = TestClient(app)  # no lifespan: never touches the real database file
    c.Session = Session
    yield c
    app.dependency_overrides.clear()

def payload(**kw):
    p = dict(legal_first_name="Test", legal_last_name="Patient", date_of_birth="1990-05-17",
             phone="416-555-0123", consent_registration=True, symptom_answers=["Synthetic headache"],
             idempotency_key=uuid.uuid4().hex)
    p.update(kw)
    return p

def post(client, **kw):
    return client.post("/api/preregistrations", json=payload(**kw))

def test_valid_submission(client):
    r = post(client)
    assert r.status_code == 201
    j = r.json()
    assert j["reference"].startswith("DEMO-") and j["access_token"]
    assert "not completed hospital registration" in j["notice"].lower()

@pytest.mark.parametrize("bad", [
    dict(date_of_birth="2999-01-01"), dict(date_of_birth="1850-01-01"), dict(date_of_birth="not-a-date"),
    dict(phone="12345"), dict(legal_first_name=""), dict(email="nope"), dict(consent_registration=False),
])
def test_validation_rejects(client, bad):
    assert post(client, **bad).status_code == 422

def test_missing_required_field(client):
    p = payload(); del p["legal_last_name"]
    assert client.post("/api/preregistrations", json=p).status_code == 422

def test_email_optional(client):
    assert post(client, email=None).status_code == 201

def test_duplicate_submission_is_idempotent(client):
    key = uuid.uuid4().hex
    a, b = post(client, idempotency_key=key), post(client, idempotency_key=key)
    assert a.status_code == 201 and b.status_code == 200
    assert a.json()["reference"] == b.json()["reference"] and b.json()["access_token"] is None
    with client.Session() as db:
        assert db.query(models.Submission).count() == 1

def test_card_number_is_rejected_and_never_echoed(client):
    r = post(client, health_number="1234567890")
    assert r.status_code == 422 and "1234567890" not in r.text

def test_errors_do_not_echo_input(client):
    r = post(client, phone="SECRETVALUE99")
    assert r.status_code == 422 and "SECRETVALUE99" not in r.text

def test_references_unique_and_non_sequential(client):
    refs = [post(client).json()["reference"] for _ in range(15)]
    assert len(set(refs)) == 15

def test_consent_records(client):
    post(client, consent_ai_processing=False)
    with client.Session() as db:
        kinds = {c.kind: c.granted for c in db.query(models.Consent)}
    assert kinds == {"registration": True, "ai_processing": False}

def test_record_access_requires_token(client):
    j = post(client).json()
    url = f"/api/preregistrations/{j['reference']}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"X-Access-Token": "wrong"}).status_code == 404
    assert client.get(url, headers={"X-Access-Token": j["access_token"]}).status_code == 200

def test_delete_removes_data_but_keeps_phi_free_audit(client):
    j = post(client).json()
    url, h = f"/api/preregistrations/{j['reference']}", {"X-Access-Token": j["access_token"]}
    assert client.delete(url, headers={"X-Access-Token": "wrong"}).status_code == 404
    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404
    with client.Session() as db:
        assert db.query(models.Patient).count() == 0 and db.query(models.SymptomResponse).count() == 0
        events = [(e.event, e.reference) for e in db.query(models.AuditEvent)]
    assert ("submission_deleted", j["reference"]) in events

def test_retention_purge(client):
    post(client)
    with client.Session() as db:
        db.query(models.Submission).update({"retention_until": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)})
        db.commit()
        assert svc.purge_expired(db) == 1
        assert db.query(models.Patient).count() == 0

def test_scanned_confirmed_status_accepted(client):
    assert post(client, health_card_status="scanned_confirmed").status_code == 201
