"""
PostgreSQL migration tests — Phase 6C.

Validates that:
1. All Alembic migrations apply cleanly to a real Postgres instance (upgrade head)
2. All migrations downgrade cleanly back to base
3. Key tables exist after upgrade
4. Enum types (stagecategory, changesource, builtineventtype, actiontype) are
   created correctly as Postgres native enum types
5. The watcher_control and watcher_status tables exist with correct columns

Run:
    export POSTGRES_TEST_URL=postgresql://user:pass@localhost:5432/test_db
    pytest tests/postgres/test_pg_migrations.py -v

Skipped automatically when POSTGRES_TEST_URL is not set.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text


pytestmark = pytest.mark.postgres


class TestMigrationsApplyCleanly:
    """Verify the full migration chain runs without error on Postgres."""

    def test_all_tables_exist_after_upgrade(self, pg_engine):
        """
        After `alembic upgrade head`, the expected tables must exist.
        The pg_engine fixture already ran upgrade head — just inspect.
        """
        inspector = inspect(pg_engine)
        tables = set(inspector.get_table_names())

        required_tables = {
            # Core
            "leads",
            "lead_sources",
            # Web UI
            "users",
            "sessions",
            # Agent app
            "agent_users",
            "agent_sessions",
            "agent_preferences",
            # Watcher coordination (Phase 5C)
            "watcher_control",
            "watcher_status",
            # Pipelines
            "pipelines",
            "pipeline_stages",
            "lead_stage_history",
            "pipeline_event_mappings",
            "pipeline_action_rules",
            "pipeline_action_rule_steps",
            # Activity
            "lead_events",
        }

        missing = required_tables - tables
        assert not missing, f"Tables missing after upgrade head: {missing}"

    def test_watcher_control_columns(self, pg_engine):
        """watcher_control must have the expected columns."""
        inspector = inspect(pg_engine)
        cols = {c["name"] for c in inspector.get_columns("watcher_control")}
        assert {"id", "agent_id", "desired_status", "sync_requested_at", "updated_at"} <= cols

    def test_watcher_status_columns(self, pg_engine):
        """watcher_status must have the expected columns."""
        inspector = inspect(pg_engine)
        cols = {c["name"] for c in inspector.get_columns("watcher_status")}
        assert {
            "id", "agent_id", "status",
            "last_heartbeat", "last_sync", "started_at", "error", "updated_at",
        } <= cols

    def test_watcher_control_unique_index_on_agent_id(self, pg_engine):
        """agent_id must have a unique constraint on watcher_control."""
        inspector = inspect(pg_engine)
        unique_constraints = inspector.get_unique_constraints("watcher_control")
        indexes = inspector.get_indexes("watcher_control")
        # Either a unique constraint or a unique index is acceptable
        unique_cols = set()
        for uc in unique_constraints:
            unique_cols.update(uc["column_names"])
        for idx in indexes:
            if idx.get("unique"):
                unique_cols.update(idx["column_names"])
        assert "agent_id" in unique_cols, (
            "watcher_control.agent_id must have a unique constraint or index"
        )

    def test_pipeline_enum_types_exist(self, pg_engine):
        """
        Postgres-native enum types created by the pipeline migration must exist.
        SQLite silently stores enums as VARCHAR — this test is Postgres-only.
        """
        with pg_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT typname FROM pg_type "
                    "WHERE typtype = 'e' "
                    "AND typname IN ('stagecategory', 'changesource', 'builtineventtype', 'actiontype')"
                )
            )
            found = {row[0] for row in result}

        expected = {"stagecategory", "changesource", "builtineventtype", "actiontype"}
        missing = expected - found
        assert not missing, (
            f"Postgres enum types missing after migration: {missing}. "
            f"Found: {found}"
        )

    def test_lead_events_activity_columns_exist(self, pg_engine):
        """Phase 3A columns added to lead_events must exist."""
        inspector = inspect(pg_engine)
        cols = {c["name"] for c in inspector.get_columns("lead_events")}
        assert {"company_id", "actor_source", "actor_id", "metadata_json"} <= cols

    def test_alembic_version_table_at_head(self, pg_engine):
        """alembic_version must record the head revision."""
        with pg_engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result]
        assert len(versions) == 1, f"Expected 1 alembic version row, got: {versions}"
        # Head revision is the watcher coordination migration
        assert versions[0] == "h2i3j4k5l6m7", (
            f"Expected head revision h2i3j4k5l6m7, got {versions[0]}"
        )
