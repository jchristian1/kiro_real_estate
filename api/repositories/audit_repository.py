"""
Audit log repository — all SQLAlchemy queries for the AuditLog domain.

Requirements: 7.1, 7.2
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from api.models.web_ui_models import AuditLog, User


class AuditRepository:
    """Data-access layer for AuditLog records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_with_filters(
        self,
        *,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AuditLog], int]:
        """Return (logs, total_count) with optional filters."""
        filters = []
        if action:
            filters.append(AuditLog.action == action)
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if start_date:
            filters.append(AuditLog.timestamp >= start_date)
        if end_date:
            filters.append(AuditLog.timestamp <= end_date)

        query = self._db.query(AuditLog)
        if filters:
            query = query.filter(and_(*filters))

        total = query.count()
        logs = (
            query.order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return logs, total

    def count_errors_since(self, cutoff: datetime) -> int:
        """Return the count of error/failed audit log entries since *cutoff*."""
        from sqlalchemy import and_
        return (
            self._db.query(AuditLog)
            .filter(
                and_(
                    AuditLog.timestamp >= cutoff,
                    AuditLog.action.like("%error%") | AuditLog.action.like("%failed%"),
                )
            )
            .count()
        )

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Return the User with the given primary key, or None."""
        return self._db.query(User).filter(User.id == user_id).first()
