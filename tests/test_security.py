import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import models
from app.database import Base, get_db
from app.main import app
from app.services import ratelimit
from app.services.auth import hash_password

PW = "correct-horse-battery"
STATIC = Path(__file__).parent.parent / "app" / "static"

@pytest.fixture
def db_client():
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
    c = TestClient(app)
    c.Session = Session
    yield c
    app.dependency_overrides.clear()

def add_user(c, name, role="clerk"):
    with c.Session() as db:
        db.add(models.StaffUser(username=name, password_hash=hash_password(PW), role=role)); db.commit()

def login(c, name, pw=PW):
    return c.post("/api/staff/login", json={"username": name, "password": pw})

def test_login_rate_limit_per_ip(db_client, monkeypatch):
    monkeypatch.setitem(ratelimit.LIMITS, "login", (3, 60))
    codes = [login(db_client, f"nobody{i}", "x").status_code for i in range(4)]
    assert codes == [401, 401, 401, 429]
    assert login(db_client, "nobody9", "x").headers["retry-after"] == "60"

def test_submission_rate_limit(db_client, monkeypatch):
    monkeypatch.setitem(ratelimit.LIMITS, "submit", (2, 60))
    def go():
        return db_client.post("/api/preregistrations", json=dict(legal_first_name="T", legal_last_name="P",
            date_of_birth="1990-01-01", phone="4165550123", consent_registration=True, idempotency_key=uuid.uuid4().hex)).status_code
    assert [go(), go(), go()] == [201, 201, 429]

def test_account_lockout_blocks_even_correct_password(db_client):
    add_user(db_client, "clerk-lock"); add_user(db_client, "clerk-other")
    for _ in range(5):
        assert login(db_client, "clerk-lock", "wrong").status_code == 401
    assert login(db_client, "clerk-lock").status_code == 429
    assert login(db_client, "clerk-other").status_code == 200
    with db_client.Session() as db:
        db.query(models.LoginAttempt).update({"created_at": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20)}); db.commit()
    assert login(db_client, "clerk-lock").status_code == 200

def test_successful_login_resets_failure_count(db_client):
    add_user(db_client, "clerk-reset")
    for _ in range(4):
        login(db_client, "clerk-reset", "wrong")
    assert login(db_client, "clerk-reset").status_code == 200
    assert [login(db_client, "clerk-reset", "wrong").status_code for _ in range(4)] == [401] * 4

def test_attempted_usernames_are_not_stored(db_client):
    login(db_client, "secret-user-name", "wrong")
    with db_client.Session() as db:
        rows = db.query(models.LoginAttempt).all()
        events = str([(e.event, e.actor, e.reference) for e in db.query(models.AuditEvent)])
    assert len(rows) == 1 and len(rows[0].key_hash) == 64 and "secret-user-name" not in events + rows[0].key_hash

@pytest.mark.parametrize("path", ["/", "/staff", "/api/symptoms/questions"])
def test_security_headers(path):
    r = TestClient(app).get(path)
    h = r.headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer" and "camera=(self)" in h["permissions-policy"]
    assert "frame-ancestors 'none'" in h["content-security-policy"] and h["cache-control"] == "no-store"
    script = [d for d in h["content-security-policy"].split(";") if d.strip().startswith("script-src")][0]
    assert "unsafe-inline" not in script and "unsafe-eval" not in script

def test_pages_have_no_inline_scripts_styles_or_handlers():
    for f in STATIC.glob("*.html"):
        t = f.read_text()
        assert not re.search(r"<script(?![^>]*\bsrc=)", t), f.name
        assert "<style" not in t and not re.search(r"\son[a-z]+\s*=", t), f.name

def test_api_docs_off_by_default():
    c = TestClient(app)
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404

def test_unhandled_errors_are_generic_and_leak_nothing():
    async def boom():
        raise ValueError("secret-phi-123")
    app.add_api_route("/__boom", boom)
    r = TestClient(app, raise_server_exceptions=False).get("/__boom")
    assert r.status_code == 500 and "secret-phi-123" not in r.text and r.headers["x-content-type-options"] == "nosniff"

def test_oversize_upload_rejected_early(db_client):
    r = db_client.post("/api/documents/card-scan", files={"file": ("c.jpg", b"\xff\xd8\xff" + b"0" * 5_200_000, "image/jpeg")})
    assert r.status_code == 413 and r.json()["detail"] == "That file is too large."
