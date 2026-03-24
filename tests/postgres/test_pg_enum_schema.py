"""
PostgreSQL enum and schema correctness tests — Phase 6C.

Validates that:
- Postgres-native enum types accept only valid values
- Inserting an invalid enum value raises an error (not silently stored as text)
- The pipeline stage category enum covers the expected values
- The lead_stage_history change_source enum covers the expected values

These behaviors are SQLite-invisible (SQLite stores enums as plain text and
never validates them).  This test suite makes them first-class.

Run:
    export POSTGRES_TEST_URL=postgresql://user:pass@localhost:5432/test_db
    pytest tests/postgres/test_pg_enum_schema.py -v

Skipped automatically when POSTGRES_TEST_URL is not set.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, ProgrammingError

pytestmark = pytest.mark.postgres


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class TestPgEnumTypes:
    """Postgres enum types must reject invalid values at the DB level."""

    def test_stagecategory_valid_values_accepted(self, pg_engine):
        """All valid stagecategory values must be insertable."""
        valid = ["open", "in_progress", "waiting", "won", "lost"]
        with pg_engine.connect() as conn:
            for val in valid:
                # Just verify the cast works — no table insert needed
                result = conn.execute(
                    text(f"SELECT '{val}'::stagecategory")
                )
                assert result.scalar() == val

    def test_stagecategory_invalid_value_rejected(self, pg_engine):
        """An invalid stagecategory value must raise a DB error."""
        with pg_engine.connect() as conn:
            with pytest.raises((DataError, ProgrammingError)):
                conn.execute(text("SELECT 'INVALID_CATEGORY'::stagecategory"))

    def test_changesource_valid_values_accepted(self, pg_engine):
        """All valid changesource values must be castable."""
        valid = ["system", "event", "automation", "manual"]
        with pg_engine.connect() as conn:
            for val in valid:
                result = conn.execute(text(f"SELECT '{val}'::changesource"))
                assert result.scalar() == val

    def test_changesource_invalid_value_rejected(self, pg_engine):
        """An invalid changesource value must raise a DB error."""
        with pg_engine.connect() as conn:
            with pytest.raises((DataError, ProgrammingError)):
                conn.execute(text("SELECT 'UNKNOWN_SOURCE'::changesource"))

    def test_actiontype_valid_values_accepted(self, pg_engine):
        """All valid actiontype values must be castable."""
        valid = [
            "send_email_template",
            "send_qualification_form",
            "send_bucket_followup_email",
            "move_to_stage",
        ]
        with pg_engine.connect() as conn:
            for val in valid:
                result = conn.execute(text(f"SELECT '{val}'::actiontype"))
                assert result.scalar() == val

    def test_builtineventtype_valid_values_accepted(self, pg_engine):
        """All valid builtineventtype values must be castable."""
        valid = [
            "lead_created",
            "response_email_sent",
            "qualification_form_sent",
            "qualification_form_submitted",
            "qualification_bucket_hot",
            "qualification_bucket_warm",
            "qualification_bucket_nurture",
        ]
        with pg_engine.connect() as conn:
            for val in valid:
                result = conn.execute(text(f"SELECT '{val}'::builtineventtype"))
                assert result.scalar() == val


class TestPgSchemaConstraints:
    """Postgres-level constraints that SQLite does not enforce."""

    def test_watcher_control_agent_id_unique_constraint_enforced(self, pg_engine):
        """
        Inserting two rows with the same agent_id must fail with a unique
        violation — not silently create a duplicate.
        """
        from sqlalchemy.exc import IntegrityError
        agent_id = f"agent_{_uid()}"
        with pg_engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO watcher_control (agent_id, desired_status, updated_at) "
                    "VALUES (:aid, 'running', NOW())"
                ),
                {"aid": agent_id},
            )
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO watcher_control (agent_id, desired_status, updated_at) "
                        "VALUES (:aid, 'stopped', NOW())"
                    ),
                    {"aid": agent_id},
                )

    def test_watcher_status_agent_id_unique_constraint_enforced(self, pg_engine):
        """Same unique constraint check for watcher_status."""
        from sqlalchemy.exc import IntegrityError
        agent_id = f"agent_{_uid()}"
        with pg_engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO watcher_status (agent_id, status, updated_at) "
                    "VALUES (:aid, 'running', NOW())"
                ),
                {"aid": agent_id},
            )
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO watcher_status (agent_id, status, updated_at) "
                        "VALUES (:aid, 'stopped', NOW())"
                    ),
                    {"aid": agent_id},
                )
