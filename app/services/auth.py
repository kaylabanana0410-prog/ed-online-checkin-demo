import hashlib, hmac, secrets

def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"

def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False

DUMMY_HASH = hash_password("not-a-real-password")  # keeps timing similar for unknown usernames

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

from datetime import datetime, timedelta, timezone
from sqlalchemy import delete

def purge_security_tables(db):
    from .. import models
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.execute(delete(models.StaffSession).where(models.StaffSession.expires_at < now))
    db.execute(delete(models.LoginAttempt).where(models.LoginAttempt.created_at < now - timedelta(days=1)))
    db.commit()
