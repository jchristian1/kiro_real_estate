"""watcher_coordination_tables

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-03-24 00:00:00.000000

Phase 5C — DB-backed watcher coordination.

Creates two tables:
  watcher_control  — API writes desired state; worker reconciles
  watcher_status   — Worker writes live status; API reads for status endpoint
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, Sequence[str], None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return inspect(conn).has_table(table_name)


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "watcher_control"):
        op.create_table(
            "watcher_control",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("agent_id", sa.String(64), nullable=False, unique=True),
            sa.Column("desired_status", sa.String(16), nullable=False, server_default="running"),
            sa.Column("sync_requested_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_watcher_control_agent_id", "watcher_control", ["agent_id"])

    if not _table_exists(conn, "watcher_status"):
        op.create_table(
            "watcher_status",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("agent_id", sa.String(64), nullable=False, unique=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="stopped"),
            sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
            sa.Column("last_sync", sa.DateTime(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_watcher_status_agent_id", "watcher_status", ["agent_id"])


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "watcher_status"):
        op.drop_index("ix_watcher_status_agent_id", table_name="watcher_status")
        op.drop_table("watcher_status")

    if _table_exists(conn, "watcher_control"):
        op.drop_index("ix_watcher_control_agent_id", table_name="watcher_control")
        op.drop_table("watcher_control")
