import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./checkin.db")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))  # configurable deletion policy
RULES_PATH = os.getenv("RULES_PATH", os.path.join(os.path.dirname(__file__), "rules", "warning_signs.json"))
MOCK_AI_MODE = os.getenv("MOCK_AI_MODE", "normal")  # normal | unavailable | uncertain
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "5000000"))
OCR_BACKEND = os.getenv("OCR_BACKEND", "mock")  # mock | tesseract (optional, needs pytesseract + Pillow + Tesseract)
MOCK_OCR_MODE = os.getenv("MOCK_OCR_MODE", "normal")  # normal | blurry | failed
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "8"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"  # set true behind HTTPS
# Destinations staff may authorize. Placeholders only: replace with names the hospital verifies.
DESTINATIONS = [d.strip() for d in os.getenv(
    "DESTINATIONS", "Main waiting area (demo placeholder);Staff will direct you (demo placeholder)").split(";") if d.strip()]
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
LOCKOUT_ATTEMPTS = int(os.getenv("LOCKOUT_ATTEMPTS", "5"))   # failed logins per username...
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))    # ...within this window triggers lockout
DEBUG_DOCS = os.getenv("DEBUG_DOCS", "false").lower() == "true"  # API docs pages are off by default
