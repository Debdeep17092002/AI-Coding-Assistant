import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Depends, HTTPException

from database.models import User
from routes.auth import get_current_user


class RateLimiter:
    """Allow at most `max_calls` per user in any `window` seconds (in memory, per process)."""

    def __init__(self, max_calls: int, window: int = 60):
        self.max_calls = max_calls
        self.window = window
        self._hits = defaultdict(deque)
        self._lock = Lock()

    def __call__(self, user: User = Depends(get_current_user)) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[user.id]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.max_calls:
                retry = int(self.window - (now - hits[0])) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Try again in {retry} seconds.",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)