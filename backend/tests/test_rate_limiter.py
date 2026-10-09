import pytest
from fastapi import HTTPException

from services.rate_limiter import RateLimiter


class FakeUser:
    def __init__(self, user_id):
        self.id = user_id


def test_blocks_after_limit_and_is_per_user():
    limiter = RateLimiter(max_calls=2, window=60)
    limiter(FakeUser(1))
    limiter(FakeUser(1))

    with pytest.raises(HTTPException) as err:
        limiter(FakeUser(1))
    assert err.value.status_code == 429

    limiter(FakeUser(2))  # a different user is not affected