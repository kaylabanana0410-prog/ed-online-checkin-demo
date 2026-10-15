import pytest
from app.services import ratelimit

@pytest.fixture(autouse=True)
def _reset_rate_limits():
    ratelimit.reset()
    yield
