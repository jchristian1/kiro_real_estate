"""
Audit log recording service.

This module provides helper functions for recording audit log entries
throughout the API. All administrative actions should be logged for
compliance and debugging purposes.

The audit log is append-only with no deletion capability.
"""

from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from api.models.web_ui_models import AuditLog


def record_audit_log(
    db_session: Session,
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[str] = None
) -> AuditLog:
    """
    Record an audit log entry.
    
    This function creates an append-only audit log record for administrative
    actions. All system changes and operations should be logged using this
    function.
    
    Args:
        db_session: SQLAlchemy database session
        user_id: ID of the user performing the action
        action: Action type (e.g., 'agent_created', 'template_updated', 'watcher_started')
        resource_type: Type of resource affected (e.g., 'agent', 'template', 'lead_source')
        resource_id: ID of the affected resource (optional)
        details: Additional details about the action (optional)
    
    Returns:
        AuditLog: The created audit log entry
    
    Example:
        >>> record_audit_log(
        ...     db_session=db,
        ...     user_id=1,
        ...     action='agent_created',
        ...     resource_type='agent',
        ...     resource_id=5,
        ...     details='Created agent agent1 with email agent1@example.com'
        ... )
    
    Requirements:
        - 7.3: Record timestamp, user, action type, and affected resource
        - 7.6: Audit log is append-only with no deletion capability
    """
    audit_entry = AuditLog(
        timestamp=datetime.utcnow(),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details
    )
    
    db_session.add(audit_entry)
    db_session.commit()
    db_session.refresh(audit_entry)
    
    return audit_entry
