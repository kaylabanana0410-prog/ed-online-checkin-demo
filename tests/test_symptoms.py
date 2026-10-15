import pytest
from fastapi.testclient import TestClient
from app.dependencies import get_ai_assistant, get_rules_engine
from app.main import app
from app.services.ai_assistant import AISummary, AIUnavailable, MockAIAssistant
from app.services.hospital_integration import MockClinicalWorkflow
from app.services.safety_rules import RulesEngine

@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()

def turn(c, *answers):
    return c.post("/api/symptoms/turn", json={"answers": list(answers)})

def test_questions(client):
    assert len(client.get("/api/symptoms/questions").json()["questions"]) == 7

@pytest.mark.parametrize("text", [
    "I have chest pain", "I can't breathe", "I CAN\u2019T BREATHE", "slurred speech since this morning",
    "heavy bleeding that won't stop", "I think I took an overdose", "my throat is swelling",
])
def test_warning_signs_trigger_911_message(client, text):
    j = turn(client, text).json()
    assert j["emergency"] and "911" in j["messages"][0]

def test_benign_text_no_warning(client):
    assert not turn(client, "mild sore throat for two days").json()["emergency"]

def test_warning_persists_across_turns(client):
    assert turn(client, "chest pain", "an hour ago").json()["emergency"]

def test_self_harm_message_has_crisis_line(client):
    assert any("9-8-8" in m for m in turn(client, "I want to kill myself").json()["messages"])

def test_flow_completes_after_all_questions(client):
    j = turn(client, *["answer"] * 7).json()
    assert j["complete"] and j["next_question"] is None

def test_rules_unavailable_fails_visibly(client):
    app.dependency_overrides[get_rules_engine] = lambda: RulesEngine.from_file("/nonexistent.json")
    j = turn(client, "mild sore throat").json()
    assert j["degraded"] and "could not check" in j["messages"][0].lower()

def test_warnings_work_when_ai_is_down(client):
    app.dependency_overrides[get_ai_assistant] = lambda: MockAIAssistant("unavailable")
    r = client.post("/api/symptoms/summary", json={"answers": ["chest pain"], "ai_consent": True})
    assert r.status_code == 200 and r.json()["emergency"] and r.json()["source"] == "fallback"

def summary(c, consent=True, answers=("Sore throat for three days, getting a bit worse, no fever",)):
    return c.post("/api/symptoms/summary", json={"answers": list(answers), "ai_consent": consent}).json()

def test_ai_summary_with_consent(client):
    j = summary(client)
    assert j["source"] == "ai" and "not a diagnosis" in j["disclaimer"]

def test_ai_not_called_without_consent(client):
    class Spy:
        called = False
        def summarize(self, a):
            Spy.called = True
            return AISummary("x", 1.0)
    app.dependency_overrides[get_ai_assistant] = Spy
    assert summary(client, consent=False)["source"] == "fallback" and not Spy.called

@pytest.mark.parametrize("mode", ["unavailable", "uncertain"])
def test_ai_unavailable_or_uncertain_falls_back(client, mode):
    app.dependency_overrides[get_ai_assistant] = lambda: MockAIAssistant(mode)
    assert summary(client)["source"] == "fallback"

def test_ai_diagnosis_language_is_blocked(client):
    class Bad:
        def summarize(self, a):
            return AISummary("You have pneumonia. It is safe to wait.", 0.99)
    app.dependency_overrides[get_ai_assistant] = Bad
    j = summary(client)
    assert j["source"] == "fallback" and "pneumonia" not in j["summary"]

def test_identity_fields_rejected_by_symptom_api(client):
    r = client.post("/api/symptoms/summary", json={"answers": ["x"], "ai_consent": True, "name": "Test Patient"})
    assert r.status_code == 422 and "Test Patient" not in r.text

def test_overlong_answer_rejected(client):
    assert turn(client, "x" * 501).status_code == 422

def test_workflow_cannot_carry_clinical_priority():
    r = MockClinicalWorkflow().submit_for_review("DEMO-X", "summary")
    assert r.status == "pending_staff_review" and not hasattr(r, "priority") and not hasattr(r, "ctas")
