"""
Agent management API endpoints.

This module provides REST API endpoints for managing Gmail agents including:
- Creating agents with encrypted credential storage
- Listing all agents (credentials excluded)
- Getting agent details
- Updating agent configuration
- Deleting agents (with watcher coordination)

All endpoints require authentication and integrate with the existing
EncryptedDBCredentialsStore from the CLI system.

Endpoints:
- POST /api/v1/agents - Create new agent
- GET /api/v1/agents - List all agents
- GET /api/v1/agents/{agent_id} - Get agent details
- PUT /api/v1/agents/{agent_id} - Update agent
- DELETE /api/v1/agents/{agent_id} - Delete agent
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
from api.models.web_ui_models import User
from api.models.agent_models import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentResponse,
    AgentListResponse,
    AgentDeleteResponse
)
from api.models.error_models import ErrorCode
from api.exceptions import (
    ValidationException,
    NotFoundException,
    ConflictException
)
from api.repositories import CredentialRepository, AgentRepository
from api.repositories.template_repository import TemplateRepository
from api.repositories.watcher_repository import AgentPreferencesRepository
from api.services.audit_log import record_audit_log
from api.config import load_config
from api.dependencies.auth import require_role


router = APIRouter(dependencies=[Depends(require_role("platform_admin"))])


# Dependencies that will be injected by FastAPI
# These are generator functions that yield the dependency
def get_db():
    """Database dependency - will be overridden in tests."""
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authentication dependency - will be overridden in tests."""
    from api.auth import get_current_user as auth_get_current_user
    return auth_get_current_user(request, db)


def _assert_agent_access(agent_id: str, current_user: User, db: Session) -> None:
    """
    Validate that the authenticated user has permission to access the specified agent.
    
    Platform admins (role='admin' or 'platform_admin') can access all agents.
    Company-scoped admins can only access agents in their own company.
    
    Raises NotFoundException if agent not found or user lacks permission.
    
    Requirements: 6.1, 6.2
    """
    from api.models.error_models import ErrorCode
    from api.exceptions import NotFoundException
    
    # Platform admins can access all agents
    if getattr(current_user, 'role', None) in ('admin', 'platform_admin'):
        return
    
    # Company-scoped admins can only access agents in their company
    cred_repo = CredentialRepository(db)
    credentials = cred_repo.get_by_agent_id(agent_id)
    
    if not credentials:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    if credentials.company_id != current_user.company_id:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )


def get_credentials_store(db: Session = Depends(get_db)) -> EncryptedDBCredentialsStore:
    """
    Create and return an EncryptedDBCredentialsStore instance.
    
    Uses the encryption key from configuration.
    
    Args:
        db: Database session
        
    Returns:
        EncryptedDBCredentialsStore instance
    """
    config = load_config()
    return EncryptedDBCredentialsStore(db, encryption_key=config.encryption_key)


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    agent_data: AgentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credentials_store: EncryptedDBCredentialsStore = Depends(get_credentials_store)
):
    """
    Create a new agent with encrypted credential storage.
    
    Stores credentials using the existing EncryptedDBCredentialsStore from
    the CLI system, ensuring compatibility and security.
    
    Args:
        agent_data: Agent creation request data
        db: Database session
        current_user: Authenticated user
        credentials_store: Encrypted credentials store
        
    Returns:
        Created agent details (credentials excluded)
        
    Raises:
        ConflictException: If agent_id already exists
        ValidationException: If email format is invalid
        
    Requirements:
        - 1.1: Provide endpoints for creating Agent records
        - 1.2: Encrypt credentials before storage
        - 21.1: Use existing gmail_lead_sync modules
        - 21.3: Preserve all existing security features
    """
    # Check if agent_id already exists
    cred_repo = CredentialRepository(db)
    existing = cred_repo.get_by_agent_id(agent_data.agent_id)
    if existing:
        raise ConflictException(
            message=f"Agent with ID '{agent_data.agent_id}' already exists",
            code=ErrorCode.CONFLICT_RESOURCE_EXISTS
        )
    
    # Store credentials using encrypted store (handles encryption automatically)
    try:
        credentials_store.store_credentials(
            agent_id=agent_data.agent_id,
            email=agent_data.email,
            app_password=agent_data.app_password
        )
    except ValueError as e:
        raise ValidationException(
            message=str(e),
            code=ErrorCode.VALIDATION_ERROR
        )
    
    # Retrieve the created credentials record
    credentials = cred_repo.get_by_agent_id(agent_data.agent_id)
    
    # Store display_name and phone if provided
    if agent_data.display_name is not None or agent_data.phone is not None or agent_data.company_id is not None:
        from api.repositories.credential_repository import CredentialUpdate
        cred_repo.update(agent_data.agent_id, CredentialUpdate(
            display_name=agent_data.display_name,
            phone=agent_data.phone,
            company_id=agent_data.company_id,
        ))
        credentials = cred_repo.get_by_agent_id(agent_data.agent_id)
    
    # Record audit log
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="agent_created",
        resource_type="agent",
        resource_id=credentials.id,
        details=f"Created agent {agent_data.agent_id}"
    )
    
    # Decrypt email for response (safe to return email, but not password)
    email = credentials_store.decrypt(credentials.email_encrypted)
    
    # Return agent details (credentials excluded)
    return AgentResponse(
        id=credentials.id,
        agent_id=credentials.agent_id,
        email=email,
        display_name=credentials.display_name,
        phone=credentials.phone,
        company_id=credentials.company_id,
        company_name=credentials.company.name if credentials.company else None,
        created_at=credentials.created_at,
        updated_at=credentials.updated_at,
        watcher_status=None
    )


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credentials_store: EncryptedDBCredentialsStore = Depends(get_credentials_store)
):
    """
    List all agents with status indicators.
    
    Platform admins see all agents. Company-scoped admins only see agents in their company.
    
    Requirements: 6.1, 6.2 - Enforce tenant isolation
    """
    from api.main import watcher_registry
    from gmail_lead_sync.agent_models import AgentUser

    cred_repo = CredentialRepository(db)
    agent_repo = AgentRepository(db)
    prefs_repo = AgentPreferencesRepository(db)

    # Get all credentials, filtered by company if user is company-scoped
    all_credentials = cred_repo.list_all()
    
    # Filter by company for company-scoped admins
    if getattr(current_user, 'role', None) not in ('admin', 'platform_admin'):
        all_credentials = [c for c in all_credentials if c.company_id == current_user.company_id]

    try:
        all_statuses = await watcher_registry.get_all_statuses()
    except Exception:
        all_statuses = {}

    agents = []
    for creds in all_credentials:
        try:
            email = credentials_store.decrypt(creds.email_encrypted)
        except (ValueError, Exception):
            email = "[decryption-error]"

        watcher_info = all_statuses.get(creds.agent_id)
        watcher_status = watcher_info["status"] if watcher_info else None

        try:
            numeric_id = int(creds.agent_id)
            au = agent_repo.get_by_id(numeric_id)
            if au:
                if not au.onboarding_completed:
                    watcher_status = "cancelled"
                elif watcher_status is None:
                    prefs = prefs_repo.get_config_by_agent_id(au.id)
                    watcher_status = "running" if (prefs and prefs.watcher_enabled) else "stopped"
        except (ValueError, TypeError):
            pass

        agents.append(AgentResponse(
            id=creds.id,
            agent_id=creds.agent_id,
            email=email,
            display_name=creds.display_name,
            phone=creds.phone,
            company_id=creds.company_id,
            company_name=creds.company.name if creds.company else None,
            created_at=creds.created_at,
            updated_at=creds.updated_at,
            watcher_status=watcher_status,
        ))

    return AgentListResponse(agents=agents)


@router.get("/agents/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credentials_store: EncryptedDBCredentialsStore = Depends(get_credentials_store)
):
    """
    Get details for a specific agent.
    
    Returns agent configuration and watcher status. Credentials are excluded
    from the response for security.
    
    Args:
        agent_id: Agent identifier
        db: Database session
        current_user: Authenticated user
        credentials_store: Encrypted credentials store
        
    Returns:
        Agent details (credentials excluded)
        
    Raises:
        NotFoundException: If agent not found or user lacks permission
        
    Requirements:
        - 1.1: Provide endpoints for reading Agent records
        - 1.3: Exclude decrypted credentials from API response
        - 1.6: Provide detail view showing Agent configuration
        - 6.1, 6.2: Enforce tenant isolation
    """
    # Validate tenant access
    _assert_agent_access(agent_id, current_user, db)
    
    # Find agent credentials
    cred_repo = CredentialRepository(db)
    credentials = cred_repo.get_by_agent_id(agent_id)
    
    if not credentials:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Decrypt email for response
    email = credentials_store.decrypt(credentials.email_encrypted)
    
    return AgentResponse(
        id=credentials.id,
        agent_id=credentials.agent_id,
        email=email,
        display_name=credentials.display_name,
        phone=credentials.phone,
        company_id=credentials.company_id,
        company_name=credentials.company.name if credentials.company else None,
        created_at=credentials.created_at,
        updated_at=credentials.updated_at,
        watcher_status=None
    )


@router.put("/agents/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    agent_data: AgentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credentials_store: EncryptedDBCredentialsStore = Depends(get_credentials_store)
):
    """
    Update an existing agent's configuration.
    
    Can update email and/or app password. Uses the existing credentials store
    which handles encryption automatically.
    
    Args:
        agent_id: Agent identifier
        agent_data: Update request data
        db: Database session
        current_user: Authenticated user
        credentials_store: Encrypted credentials store
        
    Returns:
        Updated agent details (credentials excluded)
        
    Raises:
        NotFoundException: If agent not found or user lacks permission
        ValidationException: If no fields to update or validation fails
        
    Requirements:
        - 1.1: Provide endpoints for updating Agent records
        - 1.2: Encrypt credentials before storage
        - 1.8: Record all Agent modification operations
        - 6.1, 6.2: Enforce tenant isolation
    """
    # Validate tenant access
    _assert_agent_access(agent_id, current_user, db)
    
    # Find agent credentials
    cred_repo = CredentialRepository(db)
    credentials = cred_repo.get_by_agent_id(agent_id)
    
    if not credentials:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Check if any fields to update
    if not agent_data.email and not agent_data.app_password and agent_data.display_name is None and agent_data.phone is None and agent_data.company_id is None:
        raise ValidationException(
            message="No fields to update",
            code=ErrorCode.VALIDATION_ERROR
        )
    
    # Get current credentials for fields not being updated
    current_email, current_password = credentials_store.get_credentials(agent_id)
    
    # Use new values if provided, otherwise keep current
    new_email = agent_data.email if agent_data.email else current_email
    new_password = agent_data.app_password if agent_data.app_password else current_password    
    # Update credentials (store_credentials handles updates automatically)
    try:
        credentials_store.store_credentials(
            agent_id=agent_id,
            email=new_email,
            app_password=new_password
        )
    except ValueError as e:
        raise ValidationException(
            message=str(e),
            code=ErrorCode.VALIDATION_ERROR
        )
    
    # Update display_name and phone if provided
    if agent_data.display_name is not None or agent_data.phone is not None or agent_data.company_id is not None:
        from api.repositories.credential_repository import CredentialUpdate
        credentials = cred_repo.update(agent_id, CredentialUpdate(
            display_name=agent_data.display_name,
            phone=agent_data.phone,
            company_id=agent_data.company_id,
        )) or credentials
    
    # Record audit log
    details = []
    if agent_data.email:
        details.append("email")
    if agent_data.app_password:
        details.append("password")
    
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="agent_updated",
        resource_type="agent",
        resource_id=credentials.id,
        details=f"Updated agent {agent_id} ({', '.join(details)})"
    )
    
    # If email or password changed, restart the watcher so it picks up new credentials
    if agent_data.email or agent_data.app_password:
        try:
            from api.main import watcher_registry
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_restart_watcher(watcher_registry, agent_id))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not restart watcher after credential update for {agent_id}: {e}")

    # Return updated agent details
    return AgentResponse(
        id=credentials.id,
        agent_id=credentials.agent_id,
        email=new_email,
        display_name=credentials.display_name,
        phone=credentials.phone,
        company_id=credentials.company_id,
        company_name=credentials.company.name if credentials.company else None,
        created_at=credentials.created_at,
        updated_at=credentials.updated_at,
        watcher_status=None
    )


async def _restart_watcher(registry, agent_id: str) -> None:
    """Stop and restart a watcher to pick up new credentials."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        status = await registry.get_status(agent_id)
        if status and status["status"] == "running":
            await registry.stop_watcher(agent_id)
            await registry.start_watcher(agent_id)
            logger.info(f"Watcher for agent {agent_id} restarted after credential update")
    except Exception as e:
        logger.error(f"Error restarting watcher for {agent_id}: {e}", exc_info=True)


@router.delete("/agents/{agent_id}", response_model=AgentDeleteResponse)
def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an agent and its credentials.
    
    Removes the agent's encrypted credentials from the database. In future
    tasks, this will also stop any running watcher for the agent.
    
    Args:
        agent_id: Agent identifier
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Success message
        
    Raises:
        NotFoundException: If agent not found or user lacks permission
        
    Requirements:
        - 1.1: Provide endpoints for deleting Agent records
        - 1.7: Stop any running Watcher when Agent is deleted
        - 1.8: Record all Agent deletion operations
        - 6.1, 6.2: Enforce tenant isolation
    """
    # Validate tenant access
    _assert_agent_access(agent_id, current_user, db)
    
    # Find agent credentials
    cred_repo = CredentialRepository(db)
    credentials = cred_repo.get_by_agent_id(agent_id)
    
    if not credentials:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # TODO (Task 9): Stop watcher if running before deleting agent
    # When the watcher controller is implemented in Task 9, add the following:
    # 1. Check if a watcher is running for this agent_id
    # 2. If running, gracefully stop the watcher process
    # 3. Wait for watcher to fully terminate before proceeding with deletion
    # Example code (to be implemented):
    #   from api.services.watcher_controller import get_watcher_registry
    #   watcher_registry = get_watcher_registry()
    #   if await watcher_registry.is_running(agent_id):
    #       await watcher_registry.stop_watcher(agent_id)
    
    # Stop watcher if running before deleting agent
    try:
        import asyncio as _asyncio
        from api.main import watcher_registry as _registry
        loop = _asyncio.get_event_loop()
        if loop.is_running():
            _asyncio.ensure_future(_registry.stop_watcher(agent_id))
    except Exception:
        pass

    # Record audit log before deletion
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="agent_deleted",
        resource_type="agent",
        resource_id=credentials.id,
        details=f"Deleted agent {agent_id}"
    )
    
    # Delete credentials
    cred_repo.delete(agent_id)

    # Also remove the matching AgentUser record (agent app account)
    try:
        from cryptography.fernet import Fernet
        config = load_config()
        fernet = Fernet(config.encryption_key.encode())
        email = fernet.decrypt(credentials.email_encrypted.encode()).decode()
        agent_repo = AgentRepository(db)
        agent_user = agent_repo.get_by_email(email)
        if agent_user:
            agent_repo.delete(agent_user.id)
    except Exception:
        pass  # Don't fail the delete if agent_user cleanup fails
    
    return AgentDeleteResponse(
        message=f"Agent '{agent_id}' deleted successfully"
    )


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}/templates  — active templates per pipeline step (admin view)
# ---------------------------------------------------------------------------

@router.get("/agents/{agent_id}/templates")
def get_agent_templates(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return ALL templates (all pipeline steps, all versions) for a given agent.
    
    Requirements: 6.1, 6.2 - Enforce tenant isolation
    """
    # Validate tenant access
    _assert_agent_access(agent_id, current_user, db)
    _PLATFORM_DEFAULTS = {
        "INITIAL_INVITE": {
            "subject": "Hi {lead_name}, let's find your perfect home",
            "body": "Hi {lead_name},\n\nI'm {agent_name} and I'd love to help you find your next home.\nPlease fill out this quick form so I can match you with the best options:\n{form_link}\n\nFeel free to reach me at {agent_phone} or {agent_email}.\n\nBest,\n{agent_name}",
            "name": "Platform Default",
        },
        "POST_HOT": {
            "subject": "Great news, {lead_name} — you're a top match!",
            "body": "Hi {lead_name},\n\nBased on your answers, you're a great fit for several listings I have in mind.\nI'll be in touch very shortly to schedule a tour.\n\n— {agent_name} | {agent_phone}",
            "name": "Platform Default",
        },
        "POST_WARM": {
            "subject": "{lead_name}, here are some options for you",
            "body": "Hi {lead_name},\n\nThanks for completing the form. I've put together a few listings that match your criteria.\nReply or call me at {agent_phone} when you're ready to take the next step.\n\n— {agent_name}",
            "name": "Platform Default",
        },
        "POST_NURTURE": {
            "subject": "Staying in touch, {lead_name}",
            "body": "Hi {lead_name},\n\nThanks for your interest. When you're ready to move forward, I'm here to help.\nYou can reach me at {agent_email} or {agent_phone}.\n\n— {agent_name}",
            "name": "Platform Default",
        },
    }
    TYPE_LABELS = {
        "INITIAL_INVITE": "Initial Outreach",
        "POST_HOT":       "Post Form — Hot",
        "POST_WARM":      "Post Form — Warm",
        "POST_NURTURE":   "Post Form — Nurture",
    }

    # Resolve agent_user from numeric agent_id
    agent_repo = AgentRepository(db)
    tmpl_repo = TemplateRepository(db)
    try:
        numeric_id = int(agent_id)
        agent_user = agent_repo.get_by_id(numeric_id)
    except (ValueError, TypeError):
        agent_user = None

    result = []
    for tmpl_type, label in TYPE_LABELS.items():
        default = _PLATFORM_DEFAULTS[tmpl_type]
        db_rows = []
        has_active = False
        if agent_user:
            db_rows = tmpl_repo.list_for_agent(agent_user.id)
            db_rows = [r for r in db_rows if r.template_type == tmpl_type]
            has_active = any(r.is_active for r in db_rows)

        result.append({
            "id": None,
            "type": tmpl_type,
            "label": label,
            "name": default["name"],
            "subject": default["subject"],
            "body": default["body"],
            "is_custom": False,
            "is_active": not has_active,
            "version": 0,
        })

        for row in db_rows:
            result.append({
                "id": row.id,
                "type": tmpl_type,
                "label": label,
                "name": row.name or "My Template",
                "subject": row.subject,
                "body": row.body,
                "is_custom": True,
                "is_active": row.is_active,
                "version": row.version,
            })

    return {"templates": result}


@router.post("/agents/{agent_id}/templates/{template_id}/activate")
def admin_activate_template(
    agent_id: str,
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: set a template as active for its pipeline step.
    
    Requirements: 6.1, 6.2 - Enforce tenant isolation
    """
    # Validate tenant access
    _assert_agent_access(agent_id, current_user, db)
    agent_repo = AgentRepository(db)
    tmpl_repo = TemplateRepository(db)

    try:
        numeric_id = int(agent_id)
        agent_user = agent_repo.get_by_id(numeric_id)
    except (ValueError, TypeError):
        agent_user = None

    if not agent_user:
        raise NotFoundException(message=f"Agent '{agent_id}' not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    row = tmpl_repo.activate(template_id, agent_user.id)
    if not row:
        raise NotFoundException(message="Template not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    return {"ok": True}


@router.delete("/agents/{agent_id}/templates/{template_id}")
def admin_delete_template(
    agent_id: str,
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: delete a specific template.
    
    Requirements: 6.1, 6.2 - Enforce tenant isolation
    """
    # Validate tenant access
    _assert_agent_access(agent_id, current_user, db)
    agent_repo = AgentRepository(db)
    tmpl_repo = TemplateRepository(db)

    try:
        numeric_id = int(agent_id)
        agent_user = agent_repo.get_by_id(numeric_id)
    except (ValueError, TypeError):
        agent_user = None

    if not agent_user:
        raise NotFoundException(message=f"Agent '{agent_id}' not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    row = tmpl_repo.delete(template_id, agent_user.id)
    if not row:
        raise NotFoundException(message="Template not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    if row.is_active:
        remaining = tmpl_repo.get_most_recent_for_type(agent_user.id, row.template_type)
        if remaining:
            tmpl_repo.activate(remaining.id, agent_user.id)

    return {"ok": True}
