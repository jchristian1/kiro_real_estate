"""
Public tokenized form submission endpoint.

Accepts buyer qualification form submissions via a single-use, expiring token
embedded in the invitation email link. No authentication required.

Endpoint:
    POST /public/buyer-qualification/{token}/submit

Rate limit: 5 requests per minute per source IP (Req 18.1, 18.2).

Requirements: 4.1, 4.2, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 17.3, 18.1, 18.2
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from gmail_lead_sync.preapproval.invitation_service import (
    TokenExpiredError,
    TokenNotFoundError,
    TokenUsedError,
)
from gmail_lead_sync.preapproval.handlers import on_buyer_form_submitted
from api.repositories.buyer_leads_repository import FormInvitationRepository

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# In-process IP rate limiter — 5 requests / 60 seconds per IP (Req 18.1, 18.3)
# ---------------------------------------------------------------------------

_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 60  # seconds

_ip_request_times: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = Lock()


def _is_rate_limited(ip: str) -> bool:
    """Return True if *ip* has exceeded the rate limit."""
    now = time.monotonic()
    with _rate_limit_lock:
        timestamps = _ip_request_times[ip]
        # Evict timestamps outside the current window
        cutoff = now - _RATE_LIMIT_WINDOW
        _ip_request_times[ip] = [t for t in timestamps if t > cutoff]
        if len(_ip_request_times[ip]) >= _RATE_LIMIT_MAX:
            return True
        _ip_request_times[ip].append(now)
        return False


def _client_ip(request: Request) -> str:
    """Extract the real client IP, honouring X-Forwarded-For if present."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class SubmitAnswersRequest(BaseModel):
    answers: dict[str, Any]
    user_agent: str | None = None
    device_type: str | None = None
    time_to_submit_seconds: int | None = None


# ---------------------------------------------------------------------------
# Database dependency (mirrors pattern used in other route modules)
# ---------------------------------------------------------------------------

def get_db():
    """Database dependency — overridden in tests."""
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/api/v1/public/buyer-qualification/{token}")
async def get_buyer_qualification_form(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Return the form questions for a given invitation token.
    No authentication required.
    """
    import hashlib, json as _json
    from datetime import datetime as _dt

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    inv_repo = FormInvitationRepository(db)
    invitation = inv_repo.get_invitation_by_token_hash(token_hash)

    if not invitation:
        return JSONResponse(status_code=404, content={"error": "Invalid link"})
    if invitation.used_at is not None:
        return JSONResponse(status_code=410, content={"error": "This link has already been used"})
    if invitation.expires_at < _dt.utcnow():
        return JSONResponse(status_code=410, content={"error": "This link has expired"})

    form_version = inv_repo.get_form_version_by_id(invitation.form_version_id)
    schema = _json.loads(form_version.schema_json)
    questions = schema if isinstance(schema, list) else schema.get("questions", [])

    return {"token": token, "questions": questions}



@router.post("/api/v1/public/buyer-qualification/{token}/submit")
async def submit_buyer_qualification(
    request: Request,
    token: str,
    body: SubmitAnswersRequest,
    db: Session = Depends(get_db),
):
    """
    Accept a buyer qualification form submission.

    No authentication required (Req 4.1).
    Rate-limited to 5 requests/minute per IP (Req 4.8, 18.1, 18.2).

    Returns:
        200  { submission_id, score: { total, bucket, explanation } }
        400  { error, details }   — validation failure (Req 4.7)
        404  { error }            — token not found (Req 4.5)
        410  { error }            — token expired or already used (Req 4.6)
        429  { error }            — rate limit exceeded (Req 4.8, 18.2)

    Error responses deliberately omit tenant-identifying information (Req 17.3).
    """
    # -- Rate limiting (Req 4.8, 18.1, 18.2) --------------------------------
    ip = _client_ip(request)
    if _is_rate_limited(ip):
        return JSONResponse(
            status_code=429,
            content={"error": "Too many requests"},
        )

    # -- Build request_metadata from body ------------------------------------
    request_metadata: dict[str, Any] = {}
    if body.user_agent is not None:
        request_metadata["user_agent"] = body.user_agent
    if body.device_type is not None:
        request_metadata["device_type"] = body.device_type
    if body.time_to_submit_seconds is not None:
        request_metadata["time_to_submit_seconds"] = body.time_to_submit_seconds

    # -- Delegate to handler -------------------------------------------------
    try:
        result = on_buyer_form_submitted(
            db=db,
            raw_token=token,
            answers_payload=body.answers,
            request_metadata=request_metadata,
        )
    except TokenNotFoundError:
        # Req 4.5, 17.3 — no tenant info in response
        return JSONResponse(
            status_code=404,
            content={"error": "Invalid submission link"},
        )
    except TokenExpiredError:
        # Req 4.6
        return JSONResponse(
            status_code=410,
            content={"error": "This link has expired"},
        )
    except TokenUsedError:
        # Req 4.6
        return JSONResponse(
            status_code=410,
            content={"error": "This link has already been used"},
        )
    except ValueError as exc:
        # Req 4.7 — answer validation failure
        logger.warning("Submission validation error for token (redacted): %s", exc)
        return JSONResponse(
            status_code=400,
            content={"error": "Validation failed", "details": str(exc)},
        )

    # Req 4.4 — 200 with submission_id and score summary
    # score may be None when no active ScoringVersion exists (Req 5.11)
    score = result.get("score")
    return JSONResponse(
        status_code=200,
        content={
            "submission_id": result["submission_id"],
            "score": {
                "total": score["total"],
                "bucket": score["bucket"],
                "explanation": score["explanation"],
            } if score else None,
        },
    )
