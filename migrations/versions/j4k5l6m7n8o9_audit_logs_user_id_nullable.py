"""make audit_logs.user_id nullable for system-generated pipeline actions

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'j4k5l6m7n8o9'
down_revision = 'i3j4k5l6m7n8'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'audit_logs', 'user_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        'audit_logs', 'user_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
