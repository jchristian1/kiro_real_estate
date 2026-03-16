"""agent_templates_multi

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-03-10 00:00:00.000000

Allow multiple templates per type per agent:
- Add `name` column to agent_templates
- Drop unique constraint uq_agent_templates_user_type
- Add index on (agent_user_id, template_type) for fast lookups
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    cols = [c["name"] for c in inspect(conn).get_columns(table_name)]
    return column_name in cols


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    indexes = [i["name"] for i in inspect(conn).get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    conn = op.get_bind()

    # Add name column
    if not _column_exists(conn, "agent_templates", "name"):
        op.add_column(
            "agent_templates",
            sa.Column("name", sa.String(length=255), nullable=True),
        )

    # Drop unique constraint (SQLite-safe: recreate table approach not needed for Postgres/SQLite via batch)
    with op.batch_alter_table("agent_templates") as batch_op:
        try:
            batch_op.drop_constraint("uq_agent_templates_user_type", type_="unique")
        except Exception:
            pass  # Already dropped or doesn't exist

    # Add non-unique index for fast lookups
    if not _index_exists(conn, "agent_templates", "ix_agent_templates_user_type"):
        op.create_index(
            "ix_agent_templates_user_type",
            "agent_templates",
            ["agent_user_id", "template_type"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _index_exists(conn, "agent_templates", "ix_agent_templates_user_type"):
        op.drop_index("ix_agent_templates_user_type", table_name="agent_templates")

    with op.batch_alter_table("agent_templates") as batch_op:
        batch_op.create_unique_constraint(
            "uq_agent_templates_user_type", ["agent_user_id", "template_type"]
        )

    if _column_exists(conn, "agent_templates", "name"):
        op.drop_column("agent_templates", "name")
