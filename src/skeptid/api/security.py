"""Security headers and token-bucket rate limiting."""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class TokenBucketRateLimiter:
    """Sliding-window token bucket rate limiter per IP address."""

    def __init__(self, requests_per_minute: int = 30) -> None:
        self.rpm = requests_per_minute
        self.records: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, custom_limit: int | None = None) -> bool:
        """Return True if under rate limit, False otherwise."""
        limit = custom_limit or self.rpm
        now = time.time()
        window_start = now - 60.0

        # Purge timestamps outside the 1-minute window
        valid_ts = [ts for ts in self.records[key] if ts > window_start]
        if len(valid_ts) >= limit:
            self.records[key] = valid_ts
            return False

        valid_ts.append(now)
        self.records[key] = valid_ts
        return True


default_limiter = TokenBucketRateLimiter(requests_per_minute=30)
video_limiter = TokenBucketRateLimiter(requests_per_minute=5)


async def check_rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing 30 req/min/IP."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not default_limiter.check(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded (30 requests/min). Please try again shortly.",
        )


async def check_video_rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing 5 req/min/IP on video processing."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not video_limiter.check(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Video rate limit exceeded (5 requests/min). Please try again shortly.",
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces essential defensive HTTP security headers on all responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "media-src 'self' data: blob:; "
            "connect-src 'self';"
        )
        return response
