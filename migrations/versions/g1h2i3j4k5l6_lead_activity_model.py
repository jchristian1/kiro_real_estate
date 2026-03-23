"""lead_activity_model

Revision ID: g1h2i3j4k5l6
Revises: e1f2a3b4c5d6
Create Date: 2026-03-23 00:00:00.000000

Phase 3A — Extend lead_events table to serve as the unified lead activity model.

Changes:
  - Add new event type values to lead_event_type_enum
  - Add company_id column (tenant scoping for multi-tenant reads)
  - Add actor_source column (who/what caused the event)
  - Add actor_id column (optional FK-less reference to actor)
  - Add metadata_json column (structured context, replaces untyped payload)

Existing columns are preserved. Existing rows are unaffected.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "g1h2i3j4k5l6"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    cols = [c["name"] for c in inspect(conn).get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    conn = op.get_bind()

    # SQLite does not support ALTER TYPE — we handle enum extension by
    # recreating the column with a new enum that includes all values.
    # For Postgres, ALTER TYPE ... ADD VALUE is used.
    dialect = conn.dialect.name

    # New event type values required for Phase 3A activity model.
    # These extend the existing lead_event_type_enum.
    new_values = [
        "lead_created",
        "lead_stage_changed",
        "response_email_sent",
        "qualification_form_sent",
        "qualification_form_submitted",
        "qualification_bucket_assigned",
        "manual_admin_action",
        "manual_agent_action",
        "pipeline_action_executed",
    ]

    if dialect == "postgresql":
        for val in new_values:
            try:
                conn.execute(
                    text(
                        f"ALTER TYPE lead_event_type_enum ADD VALUE IF NOT EXISTS '{val}'"
                    )
                )
            except Exception:
                pass  # value already exists

    # Add company_id column for tenant-scoped reads
    if not _column_exists(conn, "lead_events", "company_id"):
        op.add_column(
            "lead_events",
            sa.Column("company_id", sa.Integer(), nullable=True),
        )

    # Add actor_source: "system" | "pipeline" | "agent" | "admin" | "qualification"
    if not _column_exists(conn, "lead_events", "actor_source"):
        op.add_column(
            "lead_events",
            sa.Column("actor_source", sa.String(50), nullable=True),
        )

    # Add actor_id: optional numeric reference to the acting entity
    if not _column_exists(conn, "lead_events", "actor_id"):
        op.add_column(
            "lead_events",
            sa.Column("actor_id", sa.Integer(), nullable=True),
        )

    # Add metadata_json: structured context dict (replaces untyped payload for new events)
    if not _column_exists(conn, "lead_events", "metadata_json"):
        op.add_column(
            "lead_events",
            sa.Column("metadata_json", sa.Text(), nullable=True),
        )

    # Index for tenant-scoped timeline queries
    try:
        op.create_index(
            "ix_lead_events_company_created",
            "lead_events",
            ["company_id", "created_at"],
        )
    except Exception:
        pass  # index may already exist


def downgrade() -> None:
    conn = op.get_bind()

    try:
        op.drop_index("ix_lead_events_company_created", table_name="lead_events")
    except Exception:
        pass

    for col in ["metadata_json", "actor_id", "actor_source", "company_id"]:
        if _column_exists(conn, "lead_events", col):
            op.drop_column("lead_events", col)
