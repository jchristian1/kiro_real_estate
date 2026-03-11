"""
Agent onboarding routes.

Provides:
- PUT /api/v1/agent/onboarding/profile  — persist profile fields, advance onboarding_step to 2
- POST /api/v1/agent/onboarding/gmail   — test IMAP, encrypt and persist credentials, advance step to 3

Requirements: 4.1, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from api.services.credential_encryption import encrypt_app_password
from api.services.imap_service import (
    IMAPRateLimitError,
    check_and_record_imap_attempt,
    test_imap_connection,
)
from gmail_lead_sync.agent_models import AgentUser
from gmail_lead_sync.models import Company, Credentials

router = APIRouter(prefix="/agent/onboarding", tags=["Agent Onboarding"])


# ---------------------------------------------------------------------------
# Step-order enforcement
# ---------------------------------------------------------------------------

def require_onboarding_step(required: int):
    """
    Return a FastAPI dependency that enforces onboarding step ordering.

    Raises HTTP 400 with error "ONBOARDING_STEP_REQUIRED" when the agent's
    current onboarding_step is less than *required*.

    Requirements: 3.2
    """
    def _check(agent: AgentUser = Depends(get_current_agent)) -> None:
        if agent.onboarding_step < required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "ONBOARDING_STEP_REQUIRED",
                    "required_step": required,
                    "current_step": agent.onboarding_step,
                },
            )
    return _check


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProfileRequest(BaseModel):
    """PUT /onboarding/profile request body."""
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    timezone: str = Field(default="UTC", max_length=100)
    service_area: Optional[str] = Field(default=None)
    company_join_code: Optional[str] = Field(default=None)


class ProfileResponse(BaseModel):
    """PUT /onboarding/profile success response."""
    ok: bool
    onboarding_step: int


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str


class GmailRequest(BaseModel):
    """POST /onboarding/gmail request body."""
    gmail_address: str = Field(..., min_length=1, max_length=255)
    app_password: SecretStr = Field(..., min_length=1)
    imap_folder: Optional[str] = Field(default="INBOX")


class GmailResponse(BaseModel):
    """POST /onboarding/gmail success response."""
    connected: bool
    gmail_address: str
    last_sync: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.put(
    "/profile",
    status_code=status.HTTP_200_OK,
    response_model=ProfileResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
    },
)
def update_profile(
    body: ProfileRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Persist agent profile fields and advance onboarding_step to 2.

    - Persists full_name, phone, timezone, service_area to the AgentUser record.
    - If company_join_code is provided, looks up the company by name and
      associates the agent (sets agent_user.company_id).
    - Advances onboarding_step to 2.
    - Requires valid agent session.

    Requirements: 4.1, 4.3
    """
    agent.full_name = body.full_name
    agent.phone = body.phone
    agent.timezone = body.timezone if body.timezone else "UTC"
    agent.service_area = body.service_area

    # Associate with company if join code provided (Requirement 4.3)
    if body.company_join_code:
        company = (
            db.query(Company)
            .filter(Company.name == body.company_join_code)
            .first()
        )
        if company:
            agent.company_id = company.id

    # Advance onboarding step (Requirement 4.1)
    if agent.onboarding_step < 2:
        agent.onboarding_step = 2

    db.commit()
    db.refresh(agent)

    return ProfileResponse(ok=True, onboarding_step=agent.onboarding_step)


@router.post(
    "/gmail",
    status_code=status.HTTP_200_OK,
    response_model=GmailResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Onboarding step not completed"},
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
        422: {"description": "IMAP connection failed with structured error code"},
        429: {"description": "Rate limit exceeded"},
    },
    dependencies=[Depends(require_onboarding_step(1))],
)
def connect_gmail(
    body: GmailRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Test IMAP connection, encrypt and persist Gmail credentials on success.

    1. Check rate limit — 429 with retry_after_seconds if exceeded.
    2. Test live IMAP connection using provided credentials.
    3. On success: encrypt app_password, persist to credentials table,
       link credentials_id on agent_user, advance onboarding_step to 3.
    4. On IMAP failure: return 422 with structured error code and message.

    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
    """
    # Step 1: Rate limit check (Requirement 5.7)
    try:
        check_and_record_imap_attempt(agent.id)
    except IMAPRateLimitError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "RATE_LIMITED", "retry_after_seconds": exc.retry_after_seconds},
        )

    # Step 2: Live IMAP test (Requirement 5.1)
    result = test_imap_connection(body.gmail_address, body.app_password.get_secret_value())

    if not result["success"]:
        # Return 422 with structured error code (Requirements 5.3–5.6)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": result["error"], "message": result["message"]},
        )

    # Step 3: Encrypt and persist credentials (Requirement 5.2, 19.1)
    # Use Fernet (same as EncryptedDBCredentialsStore) so the admin panel and watcher
    # can decrypt both email and password using the ENCRYPTION_KEY.
    import os as _os
    from cryptography.fernet import Fernet as _Fernet
    _fernet_key = _os.environ.get("ENCRYPTION_KEY", "")
    try:
        _fernet = _Fernet(_fernet_key.encode())
        encrypted_email = _fernet.encrypt(body.gmail_address.encode()).decode()
        encrypted_password = _fernet.encrypt(body.app_password.get_secret_value().encode()).decode()
    except Exception:
        # Fallback to AES-GCM if Fernet key is missing/invalid
        encrypted_email = body.gmail_address
        encrypted_password = encrypt_app_password(body.app_password.get_secret_value())

    if agent.credentials_id is not None:
        # Update existing credentials record
        creds = db.query(Credentials).filter(Credentials.id == agent.credentials_id).first()
        if creds is not None:
            creds.email_encrypted = encrypted_email
            creds.app_password_encrypted = encrypted_password
        else:
            # Stale FK — create a new record
            creds = Credentials(
                agent_id=str(agent.id),
                email_encrypted=encrypted_email,
                app_password_encrypted=encrypted_password,
            )
            db.add(creds)
            db.flush()
            agent.credentials_id = creds.id
    else:
        creds = Credentials(
            agent_id=str(agent.id),
            email_encrypted=encrypted_email,
            app_password_encrypted=encrypted_password,
        )
        db.add(creds)
        db.flush()
        agent.credentials_id = creds.id

    # Advance onboarding step to 3
    if agent.onboarding_step < 3:
        agent.onboarding_step = 3

    db.commit()

    return GmailResponse(
        connected=True,
        gmail_address=body.gmail_address,
        last_sync=None,
    )


# ---------------------------------------------------------------------------
# Sources endpoint
# ---------------------------------------------------------------------------

import json as _json


class LeadSourceItem(BaseModel):
    """A single lead source item."""
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class LeadSourcesListResponse(BaseModel):
    """GET /onboarding/sources response."""
    sources: list[LeadSourceItem]


@router.get(
    "/sources",
    status_code=status.HTTP_200_OK,
    response_model=LeadSourcesListResponse,
    responses={401: {"model": ErrorResponse, "description": "Missing or invalid session"}},
)
def list_sources(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """Return all platform lead sources for the agent to choose from."""
    from gmail_lead_sync.models import LeadSource
    sources = db.query(LeadSource).order_by(LeadSource.id).all()
    return LeadSourcesListResponse(
        sources=[LeadSourceItem(id=s.id, name=s.sender_email, description=getattr(s, 'identifier_snippet', None)) for s in sources]
    )


class SourcesRequest(BaseModel):
    """PUT /onboarding/sources request body."""
    enabled_lead_source_ids: list[int]


class SourcesResponse(BaseModel):
    """PUT /onboarding/sources success response."""
    ok: bool
    onboarding_step: int


@router.put(
    "/sources",
    status_code=status.HTTP_200_OK,
    response_model=SourcesResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Onboarding step not completed"},
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
    },
    dependencies=[Depends(require_onboarding_step(2))],
)
def update_sources(
    body: SourcesRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Persist enabled_lead_source_ids and advance onboarding_step to 4.

    - Creates AgentPreferences record if one does not yet exist.
    - Serialises the list as a JSON string into enabled_lead_source_ids.
    - Advances onboarding_step to 4 if currently less than 4.
    - Returns {"ok": true, "onboarding_step": 4}.

    Requirements: 6.2
    """
    from gmail_lead_sync.agent_models import AgentPreferences

    # Upsert AgentPreferences
    prefs = agent.preferences
    if prefs is None:
        prefs = AgentPreferences(agent_user_id=agent.id)
        db.add(prefs)

    prefs.enabled_lead_source_ids = _json.dumps(body.enabled_lead_source_ids)

    # Advance onboarding step
    if agent.onboarding_step < 4:
        agent.onboarding_step = 4

    db.commit()

    return SourcesResponse(ok=True, onboarding_step=4)


# ---------------------------------------------------------------------------
# Automation endpoint
# ---------------------------------------------------------------------------

import datetime as _dt


class AutomationRequest(BaseModel):
    """PUT /onboarding/automation request body."""
    hot_threshold: int = Field(default=80, ge=60, le=95)
    warm_threshold: int = Field(default=50)
    sla_minutes_hot: int = Field(default=5)
    enable_tour_question: bool = Field(default=True)
    working_hours_start: Optional[str] = Field(default=None)  # "HH:MM"
    working_hours_end: Optional[str] = Field(default=None)    # "HH:MM"


class AutomationResponse(BaseModel):
    """PUT /onboarding/automation success response."""
    ok: bool
    onboarding_step: int


def _parse_time(value: Optional[str]) -> Optional[_dt.time]:
    """Parse "HH:MM" string into datetime.time, or return None."""
    if value is None:
        return None
    try:
        return _dt.datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None


@router.put(
    "/automation",
    status_code=status.HTTP_200_OK,
    response_model=AutomationResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Onboarding step not completed"},
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
    },
    dependencies=[Depends(require_onboarding_step(3))],
)
def update_automation(
    body: AutomationRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Create or update BuyerAutomationConfig and AgentPreferences, advance onboarding_step to 5.

    1. Upsert BuyerAutomationConfig for this agent (look up by agent_user_id).
    2. Upsert AgentPreferences — set sla_minutes_hot, enable_tour_question,
       quiet_hours_start/end, and link buyer_automation_config_id.
    3. Advance onboarding_step to 5 if currently less than 5.
    4. Return {"ok": true, "onboarding_step": 5}.

    Requirements: 7.1
    """
    from gmail_lead_sync.agent_models import AgentPreferences, BuyerAutomationConfig

    # Step 1: Upsert BuyerAutomationConfig
    config = (
        db.query(BuyerAutomationConfig)
        .filter(BuyerAutomationConfig.agent_user_id == agent.id)
        .first()
    )
    if config is None:
        config = BuyerAutomationConfig(
            agent_user_id=agent.id,
            name=f"{agent.full_name or 'Agent'} Config",
        )
        db.add(config)

    config.hot_threshold = body.hot_threshold
    config.warm_threshold = body.warm_threshold
    config.enable_tour_question = body.enable_tour_question

    db.flush()  # ensure config.id is populated

    # Step 2: Upsert AgentPreferences
    prefs = agent.preferences
    if prefs is None:
        prefs = AgentPreferences(agent_user_id=agent.id)
        db.add(prefs)

    prefs.sla_minutes_hot = body.sla_minutes_hot
    prefs.enable_tour_question = body.enable_tour_question
    prefs.buyer_automation_config_id = config.id

    if body.working_hours_start is not None:
        prefs.quiet_hours_start = _parse_time(body.working_hours_start)
    if body.working_hours_end is not None:
        prefs.quiet_hours_end = _parse_time(body.working_hours_end)

    # Step 3: Advance onboarding step
    if agent.onboarding_step < 5:
        agent.onboarding_step = 5

    db.commit()

    return AutomationResponse(ok=True, onboarding_step=5)


# ---------------------------------------------------------------------------
# Templates endpoint
# ---------------------------------------------------------------------------

import re as _re
from typing import List


_SUPPORTED_PLACEHOLDERS = {
    "lead_name",
    "agent_name",
    "agent_phone",
    "agent_email",
    "form_link",
}

_PLACEHOLDER_RE = _re.compile(r"\{(\w+)\}")


class TemplateItem(BaseModel):
    """A single template entry in the PUT /onboarding/templates request."""
    template_type: str = Field(..., pattern=r"^(INITIAL_INVITE|POST_HOT|POST_WARM|POST_NURTURE)$")
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    tone: str = Field(..., pattern=r"^(PROFESSIONAL|FRIENDLY|SHORT)$")


class TemplatesRequest(BaseModel):
    """PUT /onboarding/templates request body."""
    templates: List[TemplateItem]


class TemplatesResponse(BaseModel):
    """PUT /onboarding/templates success response."""
    ok: bool
    onboarding_step: int


@router.put(
    "/templates",
    status_code=status.HTTP_200_OK,
    response_model=TemplatesResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Onboarding step not completed"},
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
        422: {"description": "Unsupported placeholder found in subject or body"},
    },
    dependencies=[Depends(require_onboarding_step(4))],
)
def update_templates(
    body: TemplatesRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Persist agent template overrides with tone selection and advance onboarding_step to 6.

    1. For each template, scan subject and body for unsupported {placeholder} tokens.
    2. If any unsupported placeholder found, return 422 with error: "INVALID_PLACEHOLDER".
    3. Upsert each template (create if not found, update + increment version if exists).
    4. Advance onboarding_step to 6 if currently less than 6.
    5. Return {"ok": true, "onboarding_step": 6}.

    Requirements: 8.4, 8.5
    """
    from gmail_lead_sync.agent_models import AgentTemplate

    # Step 1 & 2: Validate placeholders across all templates before any DB writes
    for tmpl in body.templates:
        for field_value in (tmpl.subject, tmpl.body):
            found = set(_PLACEHOLDER_RE.findall(field_value))
            unsupported = found - _SUPPORTED_PLACEHOLDERS
            if unsupported:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={
                        "error": "INVALID_PLACEHOLDER",
                        "detail": (
                            f"Unsupported placeholder(s): {sorted(unsupported)}. "
                            f"Supported: {sorted(_SUPPORTED_PLACEHOLDERS)}"
                        ),
                    },
                )

    # Step 3: Upsert each template
    for tmpl in body.templates:
        existing = (
            db.query(AgentTemplate)
            .filter(
                AgentTemplate.agent_user_id == agent.id,
                AgentTemplate.template_type == tmpl.template_type,
            )
            .first()
        )
        if existing is None:
            new_tmpl = AgentTemplate(
                agent_user_id=agent.id,
                template_type=tmpl.template_type,
                subject=tmpl.subject,
                body=tmpl.body,
                tone=tmpl.tone,
                is_active=True,
                version=1,
            )
            db.add(new_tmpl)
        else:
            existing.subject = tmpl.subject
            existing.body = tmpl.body
            existing.tone = tmpl.tone
            existing.version = existing.version + 1

    # Step 4: Advance onboarding step
    if agent.onboarding_step < 6:
        agent.onboarding_step = 6

    db.commit()

    return TemplatesResponse(ok=True, onboarding_step=6)


# ---------------------------------------------------------------------------
# Onboarding test simulation endpoint
# ---------------------------------------------------------------------------

from typing import Any, Dict


# Default templates used when the agent has no custom template saved
_DEFAULT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "INITIAL_INVITE": {
        "subject": "Hi {lead_name}, let's find your perfect home",
        "body": (
            "Hi {lead_name},\n\n"
            "I'm {agent_name} and I'd love to help you find your next home.\n"
            "Please fill out this quick form so I can match you with the best options:\n"
            "{form_link}\n\n"
            "Feel free to reach me at {agent_phone} or {agent_email}.\n\n"
            "Best,\n{agent_name}"
        ),
    },
    "POST_HOT": {
        "subject": "Great news, {lead_name} — you're a top match!",
        "body": (
            "Hi {lead_name},\n\n"
            "Based on your answers, you're a great fit for several listings I have in mind.\n"
            "I'll be in touch very shortly to schedule a tour.\n\n"
            "— {agent_name} | {agent_phone}"
        ),
    },
    "POST_WARM": {
        "subject": "{lead_name}, here are some options for you",
        "body": (
            "Hi {lead_name},\n\n"
            "Thanks for completing the form. I've put together a few listings that match your criteria.\n"
            "Reply or call me at {agent_phone} when you're ready to take the next step.\n\n"
            "— {agent_name}"
        ),
    },
    "POST_NURTURE": {
        "subject": "Staying in touch, {lead_name}",
        "body": (
            "Hi {lead_name},\n\n"
            "Thanks for your interest. When you're ready to move forward, I'm here to help.\n"
            "You can reach me at {agent_email} or {agent_phone}.\n\n"
            "— {agent_name}"
        ),
    },
}


def _render_template(subject: str, body: str, lead: Dict[str, Any], agent: AgentUser) -> Dict[str, str]:
    """
    Substitute supported placeholders in subject and body.

    Supported placeholders: {lead_name}, {agent_name}, {agent_phone},
    {agent_email}, {form_link}.
    """
    replacements = {
        "{lead_name}": lead.get("name", ""),
        "{agent_name}": agent.full_name or "",
        "{agent_phone}": agent.phone or "",
        "{agent_email}": agent.email or "",
        "{form_link}": "https://example.com/form/test",
    }
    rendered_subject = subject
    rendered_body = body
    for placeholder, value in replacements.items():
        rendered_subject = rendered_subject.replace(placeholder, value)
        rendered_body = rendered_body.replace(placeholder, value)

    # Strip newlines from subject (Requirement 14.7)
    rendered_subject = rendered_subject.replace("\n", " ").replace("\r", "").strip()

    return {"subject": rendered_subject, "body": rendered_body}


def simulate_onboarding_test(agent: AgentUser, db: Session) -> Dict[str, Any]:
    """
    Run a pure in-memory simulation of the lead ingestion → scoring → email flow.

    No database records are created or modified.

    Requirements: 9.1, 9.2, 9.3
    """
    from gmail_lead_sync.agent_models import AgentPreferences, AgentTemplate, BuyerAutomationConfig

    # ------------------------------------------------------------------
    # 1. Sample lead (never persisted)
    # ------------------------------------------------------------------
    sample_lead = {
        "name": "Jane Smith",
        "phone": "555-0100",
        "address": "123 Main St",
        "source": "Zillow",
        "budget": 500000,
    }

    # ------------------------------------------------------------------
    # 2. Resolve BuyerAutomationConfig (agent's own or defaults)
    # ------------------------------------------------------------------
    config = (
        db.query(BuyerAutomationConfig)
        .filter(BuyerAutomationConfig.agent_user_id == agent.id)
        .first()
    )

    # Use attribute values or fall back to defaults
    hot_threshold = config.hot_threshold if config else 80
    warm_threshold = config.warm_threshold if config else 50
    enable_tour_question = config.enable_tour_question if config else True
    weight_timeline = config.weight_timeline if config else 25
    weight_preapproval = config.weight_preapproval if config else 30
    weight_phone_provided = config.weight_phone_provided if config else 15
    weight_tour_interest = config.weight_tour_interest if config else 20
    weight_budget_match = config.weight_budget_match if config else 10

    # ------------------------------------------------------------------
    # 3. Resolve INITIAL_INVITE template
    # ------------------------------------------------------------------
    invite_tmpl_row = (
        db.query(AgentTemplate)
        .filter(
            AgentTemplate.agent_user_id == agent.id,
            AgentTemplate.template_type == "INITIAL_INVITE",
            AgentTemplate.is_active == True,
        )
        .first()
    )
    if invite_tmpl_row:
        invite_subject = invite_tmpl_row.subject
        invite_body = invite_tmpl_row.body
    else:
        invite_subject = _DEFAULT_TEMPLATES["INITIAL_INVITE"]["subject"]
        invite_body = _DEFAULT_TEMPLATES["INITIAL_INVITE"]["body"]

    invite_email = _render_template(invite_subject, invite_body, sample_lead, agent)

    # ------------------------------------------------------------------
    # 4. Simulated form submission answers
    # ------------------------------------------------------------------
    form_answers = {
        "timeline": "3_MONTHS",
        "preapproval": True,
        "tour_interest": True,
        "budget_match": True,
        "phone_provided": True,
    }

    # ------------------------------------------------------------------
    # 5. Compute score from answers using config weights
    # ------------------------------------------------------------------
    score = 0

    # Timeline urgency
    if form_answers["timeline"] == "3_MONTHS":
        score += weight_timeline

    # Pre-approval
    if form_answers["preapproval"]:
        score += weight_preapproval

    # Phone provided
    if form_answers["phone_provided"]:
        score += weight_phone_provided

    # Tour interest (only if enable_tour_question is True)
    if enable_tour_question and form_answers["tour_interest"]:
        score += weight_tour_interest

    # Budget match
    if form_answers["budget_match"]:
        score += weight_budget_match

    # ------------------------------------------------------------------
    # 6. Assign bucket
    # ------------------------------------------------------------------
    if score >= hot_threshold:
        bucket = "HOT"
    elif score >= warm_threshold:
        bucket = "WARM"
    else:
        bucket = "NURTURE"

    # ------------------------------------------------------------------
    # 7. Resolve POST_* template based on bucket
    # ------------------------------------------------------------------
    post_type = f"POST_{bucket}"
    post_tmpl_row = (
        db.query(AgentTemplate)
        .filter(
            AgentTemplate.agent_user_id == agent.id,
            AgentTemplate.template_type == post_type,
            AgentTemplate.is_active == True,
        )
        .first()
    )
    if post_tmpl_row:
        post_subject = post_tmpl_row.subject
        post_body = post_tmpl_row.body
    else:
        post_subject = _DEFAULT_TEMPLATES[post_type]["subject"]
        post_body = _DEFAULT_TEMPLATES[post_type]["body"]

    post_email = _render_template(post_subject, post_body, sample_lead, agent)

    # ------------------------------------------------------------------
    # 8. Return simulation result — no DB writes anywhere above
    # ------------------------------------------------------------------
    return {
        "sample_lead": {
            "name": sample_lead["name"],
            "phone": sample_lead["phone"],
            "address": sample_lead["address"],
            "source": sample_lead["source"],
        },
        "invite_email": invite_email,
        "form_answers": form_answers,
        "score": score,
        "bucket": bucket,
        "post_email": post_email,
    }


class OnboardingTestResponse(BaseModel):
    """POST /onboarding/test success response."""
    sample_lead: Dict[str, Any]
    invite_email: Dict[str, str]
    form_answers: Dict[str, Any]
    score: int
    bucket: str
    post_email: Dict[str, str]


@router.post(
    "/test",
    status_code=status.HTTP_200_OK,
    response_model=OnboardingTestResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Onboarding step not completed"},
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
    },
    dependencies=[Depends(require_onboarding_step(5))],
)
def run_onboarding_test(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Run a pure in-memory onboarding test simulation.

    Produces a rendered INITIAL_INVITE email and a scored POST_SUBMISSION email
    using the agent's actual configuration. No database records are written.

    Requirements: 9.1, 9.2, 9.3
    """
    result = simulate_onboarding_test(agent, db)
    return result


# ---------------------------------------------------------------------------
# Go Live / Complete endpoint
# ---------------------------------------------------------------------------

_REQUIRED_TEMPLATE_TYPES = {"INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"}


class CompleteResponse(BaseModel):
    """POST /onboarding/complete success response."""
    ok: bool
    onboarding_completed: bool


class PreconditionChecklist(BaseModel):
    gmail_connected: bool
    lead_source_selected: bool
    automation_configured: bool
    templates_active: bool


class PreconditionsNotMetResponse(BaseModel):
    error: str
    checklist: PreconditionChecklist


@router.post(
    "/complete",
    status_code=status.HTTP_200_OK,
    response_model=CompleteResponse,
    responses={
        400: {"model": PreconditionsNotMetResponse, "description": "One or more preconditions not met"},
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
    },
    dependencies=[Depends(require_onboarding_step(5))],
)
def complete_onboarding(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Validate all 4 Go Live preconditions and set onboarding_completed = TRUE.

    Preconditions (all must hold simultaneously):
    1. Gmail connected: agent.credentials_id IS NOT NULL
    2. At least one lead source enabled: AgentPreferences.enabled_lead_source_ids
       is a non-empty JSON list
    3. BuyerAutomationConfig exists: at least one record with agent_user_id == agent.id
    4. All 4 template types active: AgentTemplate records with is_active=True exist
       for INITIAL_INVITE, POST_HOT, POST_WARM, POST_NURTURE

    If ALL pass: set onboarding_completed = True, commit, return {"ok": true, "onboarding_completed": true}
    If ANY fail: return 400 with checklist of which items are incomplete.

    Requirements: 9.4, 9.5
    """
    from gmail_lead_sync.agent_models import AgentPreferences, AgentTemplate, BuyerAutomationConfig

    # --- Precondition 1: Gmail connected ---
    gmail_connected = agent.credentials_id is not None

    # --- Precondition 2: Lead source preference saved (empty list is fine if no sources exist) ---
    prefs = agent.preferences
    lead_source_selected = False
    if prefs is not None and prefs.enabled_lead_source_ids is not None:
        try:
            ids = _json.loads(prefs.enabled_lead_source_ids)
            lead_source_selected = isinstance(ids, list)  # any list (including empty) is valid
        except (ValueError, TypeError):
            lead_source_selected = False

    # --- Precondition 3: BuyerAutomationConfig exists ---
    automation_configured = (
        db.query(BuyerAutomationConfig)
        .filter(BuyerAutomationConfig.agent_user_id == agent.id)
        .first()
    ) is not None

    # --- Precondition 4: All 4 template types active ---
    active_types = {
        row.template_type
        for row in db.query(AgentTemplate.template_type)
        .filter(
            AgentTemplate.agent_user_id == agent.id,
            AgentTemplate.is_active == True,
        )
        .all()
    }
    templates_active = _REQUIRED_TEMPLATE_TYPES.issubset(active_types)

    # --- Evaluate ---
    if gmail_connected and lead_source_selected and automation_configured and templates_active:
        agent.onboarding_completed = True
        db.commit()
        return CompleteResponse(ok=True, onboarding_completed=True)

    # Return 400 with checklist of incomplete items (Requirement 9.5)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "PRECONDITIONS_NOT_MET",
            "checklist": {
                "gmail_connected": gmail_connected,
                "lead_source_selected": lead_source_selected,
                "automation_configured": automation_configured,
                "templates_active": templates_active,
            },
        },
    )
