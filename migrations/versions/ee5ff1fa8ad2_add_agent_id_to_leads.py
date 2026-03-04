"""add_agent_id_to_leads

Revision ID: ee5ff1fa8ad2
Revises: 9a1c31e67d3a
Create Date: 2026-03-03 21:50:50.359823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee5ff1fa8ad2'
down_revision: Union[str, Sequence[str], None] = '9a1c31e67d3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('leads', sa.Column('agent_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_leads_agent_id'), 'leads', ['agent_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_leads_agent_id'), table_name='leads')
    op.drop_column('leads', 'agent_id')
