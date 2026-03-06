"""add_current_state_to_leads

Revision ID: a1b2c3d4e5f6
Revises: ee5ff1fa8ad2
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'ee5ff1fa8ad2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add current_state and current_state_updated_at columns to leads table."""
    op.add_column('leads', sa.Column('current_state', sa.String(length=50), nullable=True))
    op.add_column('leads', sa.Column('current_state_updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove current_state and current_state_updated_at columns from leads table."""
    op.drop_column('leads', 'current_state_updated_at')
    op.drop_column('leads', 'current_state')
