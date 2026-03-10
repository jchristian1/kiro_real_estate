"""add_agent_app_tables

Revision ID: c1d2e3f4a5b6
Revises: b2c3d4e5f6a7, ed911637cb7a
Create Date: 2025-01-03 00:00:00.000000

Creates all agent-app tables and adds new columns to the leads table.

New tables:
  - agent_users
  - agent_sessions
  - agent_preferences
  - buyer_automation_configs
  - agent_templates
  - lead_events

New columns on leads:
  - property_address, listing_url, score, score_bucket, score_breakdown
  - agent_current_state, agent_user_id, lead_source_name, last_agent_action_at

Requirements: 1.1, 13.7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = ("b2c3d4e5f6a7", "ed911637cb7a")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    return inspect(conn).has_table(table_name)


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    cols = [c["name"] for c in inspect(conn).get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. agent_users
    # ------------------------------------------------------------------
    if not _table_exists(conn, "agent_users"):
        op.create_table(
            "agent_users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("timezone", sa.String(length=100), nullable=False, server_default="UTC"),
            sa.Column("service_area", sa.Text(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=True),
            sa.Column("credentials_id", sa.Integer(), nullable=True),
            sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("onboarding_step", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("role", sa.String(length=50), nullable=False, server_default="agent"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
            sa.ForeignKeyConstraint(["credentials_id"], ["credentials.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )

    # ------------------------------------------------------------------
    # 2. buyer_automation_configs  (must exist before agent_preferences FK)
    # ------------------------------------------------------------------
    if not _table_exists(conn, "buyer_automation_configs"):
        op.create_table(
            "buyer_automation_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("agent_user_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("is_platform_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("hot_threshold", sa.Integer(), nullable=False, server_default="80"),
            sa.Column("warm_threshold", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("weight_timeline", sa.Integer(), nullable=False, server_default="25"),
            sa.Column("weight_preapproval", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("weight_phone_provided", sa.Integer(), nullable=False, server_default="15"),
            sa.Column("weight_tour_interest", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("weight_budget_match", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("enable_tour_question", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("form_link_template", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["agent_user_id"], ["agent_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # ------------------------------------------------------------------
    # 3. agent_sessions
    # ------------------------------------------------------------------
    if not _table_exists(conn, "agent_sessions"):
        op.create_table(
            "agent_sessions",
            sa.Column("id", sa.String(length=128), nullable=False),
            sa.Column("agent_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("last_accessed", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["agent_user_id"], ["agent_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_sessions_agent_user_id", "agent_sessions", ["agent_user_id"])
        op.create_index("ix_agent_sessions_expires_at", "agent_sessions", ["expires_at"])

    # ------------------------------------------------------------------
    # 4. agent_preferences
    # ------------------------------------------------------------------
    if not _table_exists(conn, "agent_preferences"):
        op.create_table(
            "agent_preferences",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("agent_user_id", sa.Integer(), nullable=False),
            sa.Column("hot_threshold", sa.Integer(), nullable=False, server_default="80"),
            sa.Column("warm_threshold", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("sla_minutes_hot", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("quiet_hours_start", sa.Time(), nullable=True),
            sa.Column("quiet_hours_end", sa.Time(), nullable=True),
            sa.Column("working_days", sa.String(length=20), nullable=False, server_default="MON-SAT"),
            sa.Column("enable_tour_question", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("enabled_lead_source_ids", sa.Text(), nullable=True),
            sa.Column("buyer_automation_config_id", sa.Integer(), nullable=True),
            sa.Column("watcher_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("watcher_admin_override", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["agent_user_id"], ["agent_users.id"]),
            sa.ForeignKeyConstraint(["buyer_automation_config_id"], ["buyer_automation_configs.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("agent_user_id"),
        )

    # ------------------------------------------------------------------
    # 5. agent_templates
    # ------------------------------------------------------------------
    if not _table_exists(conn, "agent_templates"):
        op.create_table(
            "agent_templates",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("agent_user_id", sa.Integer(), nullable=False),
            sa.Column(
                "template_type",
                sa.Enum(
                    "INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE",
                    name="agent_template_type_enum",
                ),
                nullable=False,
            ),
            sa.Column("subject", sa.String(length=500), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column(
                "tone",
                sa.Enum("PROFESSIONAL", "FRIENDLY", "SHORT", name="agent_template_tone_enum"),
                nullable=False,
                server_default="PROFESSIONAL",
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("parent_template_id", sa.Integer(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["agent_user_id"], ["agent_users.id"]),
            sa.ForeignKeyConstraint(["parent_template_id"], ["templates.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("agent_user_id", "template_type", name="uq_agent_templates_user_type"),
        )

    # ------------------------------------------------------------------
    # 6. lead_events
    # ------------------------------------------------------------------
    if not _table_exists(conn, "lead_events"):
        op.create_table(
            "lead_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("agent_user_id", sa.Integer(), nullable=True),
            sa.Column(
                "event_type",
                sa.Enum(
                    "EMAIL_RECEIVED",
                    "LEAD_PARSED",
                    "INVITE_CREATED",
                    "INVITE_SENT",
                    "FORM_SUBMITTED",
                    "LEAD_SCORED",
                    "POST_EMAIL_SENT",
                    "AGENT_CONTACTED",
                    "APPOINTMENT_SET",
                    "LEAD_LOST",
                    "LEAD_CLOSED",
                    "NOTE_ADDED",
                    "STATUS_CHANGED",
                    "WATCHER_TOGGLED",
                    name="lead_event_type_enum",
                ),
                nullable=False,
            ),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["agent_user_id"], ["agent_users.id"]),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_lead_events_lead_id_created_at", "lead_events", ["lead_id", "created_at"]
        )

    # ------------------------------------------------------------------
    # 7. New columns on leads table
    # ------------------------------------------------------------------
    if not _column_exists(conn, "leads", "property_address"):
        op.add_column("leads", sa.Column("property_address", sa.String(length=500), nullable=True))
    if not _column_exists(conn, "leads", "listing_url"):
        op.add_column("leads", sa.Column("listing_url", sa.String(length=1000), nullable=True))
    if not _column_exists(conn, "leads", "score"):
        op.add_column("leads", sa.Column("score", sa.Integer(), nullable=True))
    if not _column_exists(conn, "leads", "score_bucket"):
        op.add_column(
            "leads",
            sa.Column(
                "score_bucket",
                sa.Enum("HOT", "WARM", "NURTURE", name="lead_score_bucket_enum"),
                nullable=True,
            ),
        )
    if not _column_exists(conn, "leads", "score_breakdown"):
        op.add_column("leads", sa.Column("score_breakdown", sa.Text(), nullable=True))
    if not _column_exists(conn, "leads", "agent_current_state"):
        op.add_column(
            "leads",
            sa.Column(
                "agent_current_state",
                sa.Enum(
                    "NEW",
                    "INVITE_SENT",
                    "FORM_SUBMITTED",
                    "SCORED",
                    "CONTACTED",
                    "APPOINTMENT_SET",
                    "LOST",
                    "CLOSED",
                    name="lead_agent_state_enum",
                ),
                nullable=True,
                server_default="NEW",
            ),
        )
    if not _column_exists(conn, "leads", "agent_user_id"):
        op.add_column("leads", sa.Column("agent_user_id", sa.Integer(), nullable=True))
    if not _column_exists(conn, "leads", "lead_source_name"):
        op.add_column("leads", sa.Column("lead_source_name", sa.String(length=100), nullable=True))
    if not _column_exists(conn, "leads", "last_agent_action_at"):
        op.add_column("leads", sa.Column("last_agent_action_at", sa.DateTime(), nullable=True))
    if not _column_exists(conn, "leads", "company_id"):
        op.add_column("leads", sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()

    # Remove leads columns (reverse order)
    for col in [
        "last_agent_action_at",
        "lead_source_name",
        "agent_user_id",
        "agent_current_state",
        "score_breakdown",
        "score_bucket",
        "score",
        "listing_url",
        "property_address",
    ]:
        if _column_exists(conn, "leads", col):
            op.drop_column("leads", col)

    # Drop tables in reverse dependency order
    if _table_exists(conn, "lead_events"):
        op.drop_index("ix_lead_events_lead_id_created_at", table_name="lead_events")
        op.drop_table("lead_events")
    if _table_exists(conn, "agent_templates"):
        op.drop_table("agent_templates")
    if _table_exists(conn, "agent_preferences"):
        op.drop_table("agent_preferences")
    if _table_exists(conn, "agent_sessions"):
        op.drop_index("ix_agent_sessions_expires_at", table_name="agent_sessions")
        op.drop_index("ix_agent_sessions_agent_user_id", table_name="agent_sessions")
        op.drop_table("agent_sessions")
    if _table_exists(conn, "buyer_automation_configs"):
        op.drop_table("buyer_automation_configs")
    if _table_exists(conn, "agent_users"):
        op.drop_table("agent_users")
