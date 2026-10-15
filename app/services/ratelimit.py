"""In-memory sliding-window limiter per client IP. Fine for one process; production needs a shared
store (e.g. Redis) and limits at the gateway too. Behind a proxy, configure trusted proxy headers."""
import threading, time
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from .. import config

LIMITS = {"login": (20, 60), "submit": (20, 600), "scan": (20, 600), "symptoms": (240, 60)}  # (max, seconds)
_hits: dict = defaultdict(deque)
_lock = threading.Lock()

def reset():
    _hits.clear()

def limit(name: str):
    def dep(request: Request):
        if not config.RATE_LIMIT_ENABLED:
            return
        mx, window = LIMITS[name]
        key, now = (name, request.client.host if request.client else "unknown"), time.monotonic()
        with _lock:
            q = _hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= mx:
                raise HTTPException(429, "Too many requests. Please wait a moment and try again.",
                                    headers={"Retry-After": str(window)})
            q.append(now)
    return dep
