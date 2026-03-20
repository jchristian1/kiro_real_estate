"""
LeadLifecycleOrchestrator — Central application-layer coordinator.

This is the single entry point for all external callers that need to trigger
lead lifecycle work:

    Watcher          → notify_lead_created(db, lead_id, context)
    PublicSubmission → notify_form_submitted(db, raw_token, answers, metadata)

The orchestrator translates these calls into the correct sequence of domain
operations without letting callers know about the pipeline engine, handlers,
or any other internal module.

Internal flow
─────────────
notify_lead_created
    └─ fire_event(lead_created)          [pipeline engine]

notify_form_submitted
    └─ on_buyer_form_submitted(...)      [qualification module]
       └─ _fire_post_submission_events   [called back into orchestrator]
          └─ fire_event(qualification_form_submitted)
          └─ fire_event(qualification_bucket_*)

No module outside this file should import fire_event or on_buyer_form_submitted
directly.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def notify_lead_created(
    db: Session,
    lead_id: int,
    context: dict,
) -> None:
    """Called by the watcher after a new lead is persisted.

    Fires the pipeline ``lead_created`` event so the pipeline engine can
    assign the initial stage and execute any matching automation rules.
    """
    try:
        from api.models.pipeline_models import BuiltInEventType
        from api.services.lead_stage_transition_engine import fire_event

        fire_event(db, lead_id, BuiltInEventType.lead_created, context)
    except Exception as exc:
        logger.warning(
            "notify_lead_created: pipeline fire_event failed for lead %s: %s",
            lead_id, exc, exc_info=True,
        )


def notify_form_submitted(
    db: Session,
    raw_token: str,
    answers_payload: dict,
    request_metadata: dict,
) -> dict:
    """Called by the public submission router after a buyer submits the form.

    Delegates to the qualification module which validates, scores, persists,
    and then calls back into this orchestrator via _fire_post_submission_events
    to trigger the pipeline events.

    Returns the same dict as on_buyer_form_submitted:
        {"submission_id": int, "score": {...} | None}

    Raises TokenNotFoundError / TokenUsedError / TokenExpiredError / ValueError
    on validation failures (callers should handle these).
    """
    from gmail_lead_sync.preapproval.handlers import on_buyer_form_submitted

    return on_buyer_form_submitted(
        db=db,
        raw_token=raw_token,
        answers_payload=answers_payload,
        request_metadata=request_metadata,
    )


def fire_post_submission_events(
    db: Session,
    lead_id: int,
    tenant_id: int,
    bucket: str | None,
) -> None:
    """Fire pipeline events after a form submission is persisted and scored.

    Called exclusively by handlers.on_buyer_form_submitted — not by external
    callers.  Kept here so the pipeline coupling lives in one place.
    """
    try:
        from api.models.pipeline_models import BuiltInEventType
        from api.services.lead_stage_transition_engine import fire_event

        fire_event(
            db, lead_id,
            BuiltInEventType.qualification_form_submitted,
            {"tenant_id": tenant_id},
        )

        if bucket is not None:
            bucket_event_map = {
                "HOT": BuiltInEventType.qualification_bucket_hot,
                "WARM": BuiltInEventType.qualification_bucket_warm,
                "NURTURE": BuiltInEventType.qualification_bucket_nurture,
            }
            bucket_event = bucket_event_map.get(bucket)
            if bucket_event:
                fire_event(db, lead_id, bucket_event, {"tenant_id": tenant_id})

    except Exception as exc:
        logger.warning(
            "fire_post_submission_events: pipeline fire_event failed for lead %s: %s",
            lead_id, exc, exc_info=True,
        )
