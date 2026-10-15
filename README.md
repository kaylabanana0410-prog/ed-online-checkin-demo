# ED Online Check-In: demonstration prototype

An unofficial prototype of AI-assisted online pre-registration for an emergency department. It uses synthetic data only. It is **not** affiliated with or approved by St. Joseph's Health Centre and must not be used with real patients. Online pre-registration is not hospital registration, a queue position, or triage.

## Quick start (Python 3.12 or newer)
    python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    pytest                                                # 80+ tests
    python -m app.manage seed-demo                        # 3 demo staff, random passwords printed ONCE
    uvicorn app.main:app --reload --port 8001
Patient flow: http://127.0.0.1:8001 · Staff console: http://127.0.0.1:8001/staff
Walkthrough: `docs/MANUAL_TEST_CHECKLIST.md`. Real staff accounts: `python -m app.manage create-staff --username NAME --role clerk|nurse|charge_nurse`. There are no default passwords.

## What it does
1. Eight-step patient journey (welcome and 911 notice, details, guided symptom chat, health card, review and consent, confirmation, in-person steps, destination).
2. Warning signs come from a configurable rules file, never from the AI. A warning never blocks the form.
3. Mock AI summary (optional consent), blocked from diagnosis or "safe to wait" wording, with a safe fallback.
4. Health card by camera or upload; OCR optional and always confirmed by the patient; images deleted immediately; numbers never stored.
5. Staff console with roles (clerk, nurse, charge nurse), reference search, labelled patient-reported / AI-generated / staff-verified sections, workflow steps, authorized destination, corrections, action log.
6. Security: scrypt passwords, cookie sessions with CSRF tokens, rate limits and lockout, strict CSP and headers, generic errors, PHI-free logs, retention purge.

## Settings (environment variables)
| Variable | Default | Purpose |
|---|---|---|
| DATABASE_URL | sqlite:///./checkin.db | Database (PostgreSQL later) |
| RETENTION_DAYS | 30 | Auto-delete submissions after this many days |
| RULES_PATH | app/rules/warning_signs.json | Hospital-approved warning rules |
| MOCK_AI_MODE | normal | normal / unavailable / uncertain |
| OCR_BACKEND, MOCK_OCR_MODE | mock, normal | mock or tesseract; normal / blurry / failed |
| MAX_UPLOAD_BYTES | 5000000 | Card image size cap |
| DESTINATIONS | two placeholders | Semicolon-separated approved destinations |
| SESSION_HOURS, COOKIE_SECURE | 8, false | Staff sessions; set true behind HTTPS |
| RATE_LIMIT_ENABLED, LOCKOUT_ATTEMPTS, LOCKOUT_MINUTES | true, 5, 15 | Abuse protection |
| DEBUG_DOCS | false | Enable /docs for development |

## Layout
    app/  main.py config.py database.py dependencies.py models.py schemas.py manage.py
      routers/   registration, symptoms, documents, staff
      services/  ai_assistant, safety_rules, symptom_questionnaire, ocr_service, hospital_integration,
                 registration_service, workflow, auth, ratelimit
      rules/     warning_signs.json (PLACEHOLDER, needs clinical review)
      static/    index.html staff.html privacy.html patient.js/css staff.js/css
    tests/  docs/  requirements.txt  .env.example

## Mocked or placeholder (replace before any real use)
AI summarizer, warning rules, OCR, health card validation, clinical workflow integration, destination names, local staff passwords, in-memory rate limiting, SQLite. See `docs/DEPLOYMENT_REQUIREMENTS.md` (requirements for hospital deployment) and `docs/PRIVACY_FRAMEWORK_PHIPA.md` (draft privacy review checklist, not legal advice).
