"""widen sessions.id to VARCHAR(128)

The session token is 64 bytes hex-encoded = 128 characters.
The original column was VARCHAR(64) which works on SQLite (no enforcement)
but raises StringDataRightTruncation on PostgreSQL.

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'i3j4k5l6m7n8'
down_revision = 'h2i3j4k5l6m7'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'sessions', 'id',
        existing_type=sa.String(64),
        type_=sa.String(128),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        'sessions', 'id',
        existing_type=sa.String(128),
        type_=sa.String(64),
        existing_nullable=False,
    )
