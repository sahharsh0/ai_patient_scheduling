"""
Rate limiting middleware.
"""
import time
from collections import defaultdict
from typing import Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.config import settings


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.

    Note: in-memory storage only rate-limits correctly within a single
    process. Running multiple uvicorn/gunicorn workers (or multiple
    container replicas) means each one tracks its own counts, so the
    effective limit becomes requests_per_minute × worker_count. For a
    multi-instance production deployment, replace `self.requests` with a
    shared store (e.g. Redis) using the same sliding-window logic.
    """

    def __init__(self, app: ASGIApp, requests_per_minute: int = None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self.window_size = 60  # seconds
        # {client_ip: [timestamp, timestamp, ...]} — one entry per request seen.
        self.requests: Dict[str, list] = defaultdict(list)
        # Bound how many distinct client_ip keys we track before pruning
        # entirely-stale ones, so long-running processes with many distinct
        # callers don't leak memory in this dict forever.
        self._max_tracked_clients = 10_000

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        timestamps = self.requests[client_ip]
        # Drop timestamps outside the sliding window.
        fresh = [ts for ts in timestamps if now - ts < self.window_size]

        if len(fresh) >= self.requests_per_minute:
            # IMPORTANT: raising HTTPException here would NOT be caught by
            # FastAPI's exception handlers — BaseHTTPMiddleware.dispatch runs
            # outside the layer that converts HTTPException into a response,
            # so it would surface as a raw 500 instead of a 429. Return the
            # response directly instead.
            self.requests[client_ip] = fresh
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per {self.window_size} seconds."
                },
            )

        fresh.append(now)
        self.requests[client_ip] = fresh

        if len(self.requests) > self._max_tracked_clients:
            self._prune_stale_clients(now)

        return await call_next(request)

    def _prune_stale_clients(self, now: float) -> None:
        """Drop client_ip entries with no requests left in the window, so the
        dict doesn't grow forever under many distinct callers."""
        stale_keys = [ip for ip, timestamps in self.requests.items() if not timestamps or now - timestamps[-1] >= self.window_size]
        for ip in stale_keys:
            del self.requests[ip]
