"""
Settings repository — all SQLAlchemy queries for the Setting domain.

Requirements: 7.1, 7.2
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from api.models.web_ui_models import Setting


class SettingsRepository:
    """Data-access layer for Setting records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_key(self, key: str) -> Optional[Setting]:
        """Return the setting with the given key, or None."""
        return self._db.query(Setting).filter(Setting.key == key).first()

    def get_value(self, key: str, default: str) -> str:
        """Return the setting value for *key*, or *default* if not found."""
        setting = self.get_by_key(key)
        return setting.value if setting else default

    def upsert(self, key: str, value: str, user_id: int) -> Setting:
        """Insert or update a setting value."""
        setting = self.get_by_key(key)
        now = datetime.utcnow()
        if setting:
            setting.value = value
            setting.updated_at = now
            setting.updated_by = user_id
        else:
            setting = Setting(
                key=key,
                value=value,
                updated_at=now,
                updated_by=user_id,
            )
            self._db.add(setting)
        self._db.commit()
        self._db.refresh(setting)
        return setting
