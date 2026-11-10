import time
from typing import Dict, Tuple
from threading import Lock
from fastapi import HTTPException, status, Request

class LoginRateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter for login attempts.
    Blocks brute-force attacks by limiting failed attempts per IP / identifier.
    """
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60, block_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._attempts: Dict[str, list[float]] = {}
        self._blocked_until: Dict[str, float] = {}
        self._lock = Lock()

    def _get_key(self, request: Request, identifier: str = "") -> str:
        client_ip = request.client.host if request.client else "127.0.0.1"
        return f"{client_ip}:{identifier.strip().lower()}"

    def check(self, request: Request, identifier: str = "") -> None:
        key = self._get_key(request, identifier)
        now = time.time()

        with self._lock:
            # Check if currently blocked
            blocked_until = self._blocked_until.get(key, 0)
            if now < blocked_until:
                retry_after = int(blocked_until - now) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Account temporarily locked for {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)}
                )

            # Purge timestamps outside sliding window
            timestamps = [t for t in self._attempts.get(key, []) if now - t < self.window_seconds]
            self._attempts[key] = timestamps

            if len(timestamps) >= self.max_attempts:
                self._blocked_until[key] = now + self.block_seconds
                self._attempts[key] = []
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Account temporarily locked for {self.block_seconds} seconds.",
                    headers={"Retry-After": str(self.block_seconds)}
                )

    def record_failure(self, request: Request, identifier: str = "") -> None:
        key = self._get_key(request, identifier)
        now = time.time()
        with self._lock:
            if key not in self._attempts:
                self._attempts[key] = []
            self._attempts[key].append(now)

    def record_success(self, request: Request, identifier: str = "") -> None:
        key = self._get_key(request, identifier)
        with self._lock:
            self._attempts.pop(key, None)
            self._blocked_until.pop(key, None)

login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=60, block_seconds=60)
