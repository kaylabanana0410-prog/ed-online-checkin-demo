import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.dependencies import get_ocr_service
from app.main import app
from app.services.ocr_service import MockOCRService, OCRField, OCRResult, parse_card_text

JPG = b"\xff\xd8\xff\xe0" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100

@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()

def scan(c, data=JPG, ctype="image/jpeg", name="card.jpg"):
    return c.post("/api/documents/card-scan", files={"file": (name, data, ctype)})

def test_valid_scan_fields_need_confirmation(client):
    r = scan(client)
    j = r.json()
    assert r.status_code == 200 and j["simulated"] and r.headers["cache-control"] == "no-store"
    assert j["fields"] and all(f["verified"] is False and f["needs_confirmation"] and "confidence" in f for f in j["fields"])

def test_png_accepted(client):
    assert scan(client, PNG, "image/png", "c.png").status_code == 200

def test_rejects_wrong_type_and_spoofed_content(client):
    assert scan(client, b"hello", "text/plain", "a.txt").status_code == 415
    assert scan(client, b"not really an image", "image/jpeg").status_code == 415

def test_rejects_oversize_and_empty(client):
    assert scan(client, JPG + b"0" * 5_000_000).status_code == 413
    assert scan(client, b"").status_code == 400

def test_blurry_image_offers_manual_entry(client):
    app.dependency_overrides[get_ocr_service] = lambda: MockOCRService("blurry")
    j = scan(client).json()
    assert j["manual_entry_needed"] and j["fields"] == [] and "blurry" in j["message"]

def test_ocr_crash_is_handled_not_500(client):
    app.dependency_overrides[get_ocr_service] = lambda: MockOCRService("failed")
    r = scan(client)
    assert r.status_code == 200 and r.json()["manual_entry_needed"] and r.json()["quality"] == "failed"

def test_temp_file_deleted_and_client_filename_unused(client):
    class Spy:
        def extract(self, path: Path):
            Spy.path, Spy.existed = path, path.exists()
            return OCRResult([OCRField("health_number", "1234567890", 0.9)])
    app.dependency_overrides[get_ocr_service] = Spy
    scan(client, name="../../evil.jpg")
    assert Spy.existed and Spy.path.name == "card.jpg"
    assert not Spy.path.exists() and not Spy.path.parent.exists()

def test_low_confidence_flagged(client):
    app.dependency_overrides[get_ocr_service] = lambda: type("L", (), {"extract": lambda s, p: OCRResult([OCRField("health_number", "1234567890", 0.4)], "low_confidence")})()
    j = scan(client).json()
    assert j["fields"][0]["confidence_label"] == "low" and "glare" in j["message"]

def test_parse_card_text():
    r = parse_card_text("ONTARIO 1234 567 890 AB VALID 2030/01/31", 0.9)
    assert {f.name: f.value for f in r.fields} == {"health_number": "1234567890", "version_code": "AB", "expiry_date": "2030-01-31"}
    assert parse_card_text("no digits here", 0.9).quality == "failed"
    assert parse_card_text("1234567890", 0.5).quality == "low_confidence"

def test_validation_is_simulated_and_masked(client):
    j = client.post("/api/documents/card-validate", json={"health_number": "1234-567-890", "version_code": "ab"}).json()
    assert j["format_valid"] and j["simulated"] and j["eligibility"] == "not_checked"
    assert j["masked_number"] == "******7890" and "1234567890" not in str(j)
    assert not client.post("/api/documents/card-validate", json={"health_number": "123"}).json()["format_valid"]
    assert client.post("/api/documents/card-validate", json={"health_number": "1", "name": "x"}).status_code == 422

