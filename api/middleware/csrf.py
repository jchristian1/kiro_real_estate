"""
Origin-based CSRF protection middleware.

Strategy: validate the Origin (or Referer fallback) header on all
state-changing requests (POST, PUT, PATCH, DELETE) against the configured
CORS_ORIGINS allowlist.

Why origin validation instead of CSRF tokens:
- The app uses HTTP-only cookies — the frontend cannot read them, so
  double-submit cookie patterns add no value.
- SameSite=strict in production already blocks cross-site cookie sending,
  but that assumption breaks if the deployment topology changes (e.g. API
  and frontend on different subdomains, or a reverse proxy strips the flag).
- Origin validation is a stateless, server-side check that works regardless
  of cookie flags and requires zero frontend changes.

Exemptions:
- GET, HEAD, OPTIONS — safe/idempotent methods, no state change.
- /api/v1/health, /metrics — public read-only endpoints.
- /api/v1/public/* — public form submission endpoints (no session cookie).
- /api/v1/auth/login, /api/v1/agent/auth/login, /api/v1/agent/auth/signup
  — login/signup endpoints: the session cookie does not exist yet, so there
  is nothing to protect via CSRF. These are already rate-limited.

References:
- OWASP CSRF Prevention Cheat Sheet (Verifying Origin With Standard Headers)
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
"""

from __future__ import annotations

import logging
from typing import Callable, Sequence
from urllib.parse import urlparse

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("api.middleware.csrf")

# Methods that change server state and therefore require origin validation.
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Paths that are exempt from origin validation.
# Login/signup: no session exists yet — nothing to CSRF-protect.
# Public submission: unauthenticated, no session cookie involved.
# Health/metrics: read-only, no session required.
_EXEMPT_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/agent/auth/login",
    "/api/v1/agent/auth/signup",
    "/api/v1/health",
    "/metrics",
})

_EXEMPT_PREFIXES = (
    "/api/v1/public/",
)


def _origin_matches(origin: str, allowed_origins: Sequence[str]) -> bool:
    """
    Return True if *origin* is in the *allowed_origins* list.

    Comparison is scheme+host+port only (path is ignored).
    Wildcard ``"*"`` in allowed_origins is intentionally NOT supported —
    a wildcard CORS origin would defeat the purpose of this check.
    """
    try:
        parsed = urlparse(origin)
        # Reconstruct scheme://host[:port] for a canonical comparison.
        canonical = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    except Exception:
        return False

    return canonical in {o.rstrip("/") for o in allowed_origins}


def _extract_origin(request: Request) -> str | None:
    """
    Return the Origin header value, or derive it from Referer as a fallback.

    Browsers always send Origin on cross-origin requests and on same-origin
    POST requests in modern browsers.  Referer is used as a fallback for
    older clients and some same-origin POST flows.
    """
    origin = request.headers.get("origin")
    if origin:
        return origin

    referer = request.headers.get("referer")
    if referer:
        try:
            parsed = urlparse(referer)
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            return None

    return None


class CSRFOriginMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces origin validation on mutating HTTP requests.

    Attach to the FastAPI app after CORS middleware:

        app.add_middleware(CSRFOriginMiddleware, allowed_origins=config.cors_origins)

    Args:
        app:             The ASGI application.
        allowed_origins: List of allowed origin strings (from CORS_ORIGINS config).
                         Must be explicit origins — wildcards are rejected.
    """

    def __init__(self, app: ASGIApp, allowed_origins: Sequence[str]) -> None:
        super().__init__(app)
        # Filter out wildcards — a wildcard origin defeats origin validation.
        self._allowed_origins: list[str] = [
            o for o in allowed_origins if o != "*"
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only check mutating methods.
        if request.method not in _MUTATING_METHODS:
            return await call_next(request)

        # Exempt specific paths.
        path = request.url.path
        if path in _EXEMPT_PATHS:
            return await call_next(request)
        if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
            return await call_next(request)

        origin = _extract_origin(request)

        if origin is None:
            # No Origin or Referer header at all.
            # This can happen with server-to-server requests (curl, Postman,
            # internal services).  We allow it here because:
            # 1. Browsers always send Origin on cross-origin POST.
            # 2. Blocking missing-origin would break legitimate API clients.
            # 3. The session cookie (HttpOnly) is still required — an attacker
            #    without a browser cannot exploit CSRF anyway.
            # If you want to enforce browser-only access, change this to reject.
            logger.debug(
                "CSRF check: no Origin/Referer header — allowing (non-browser client)",
                extra={"path": path, "method": request.method},
            )
            return await call_next(request)

        if not _origin_matches(origin, self._allowed_origins):
            logger.warning(
                "CSRF origin mismatch — request blocked",
                extra={
                    "path": path,
                    "method": request.method,
                    "origin": origin,
                    "allowed_origins": self._allowed_origins,
                },
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden",
                    "message": "Request origin is not allowed.",
                    "code": "CSRF_ORIGIN_MISMATCH",
                },
            )

        return await call_next(request)
