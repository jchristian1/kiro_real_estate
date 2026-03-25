"""Add processed_messages table

Revision ID: a1cc62a1c4a6
Revises: d2e3f4a5b6c7
Create Date: 2026-03-12 12:34:43.348195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1cc62a1c4a6'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — only creates processed_messages table.

    NOTE: The destructive drop_table / drop_column statements that were
    auto-generated here have been intentionally removed.  Those tables
    (agent_users, form_templates, etc.) are created by earlier migrations
    and must not be dropped here.
    """
    # Use bind to check if table already exists (idempotent for re-runs)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'processed_messages' not in existing_tables:
        op.create_table(
            'processed_messages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('agent_id', sa.String(length=255), nullable=False),
            sa.Column('message_id_hash', sa.String(length=64), nullable=False),
            sa.Column('processed_at', sa.DateTime(), nullable=False),
            sa.Column('lead_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('agent_id', 'message_id_hash', name='uq_processed_message'),
        )
        op.create_index('idx_processed_messages_agent', 'processed_messages', ['agent_id'], unique=False)
        op.create_index('idx_processed_messages_hash', 'processed_messages', ['message_id_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema — only drops processed_messages table.

    The auto-generated downgrade was incorrect: it tried to re-add columns
    and tables that belong to other migrations.  This downgrade only reverses
    what upgrade() actually does (creating processed_messages).
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'processed_messages' in existing_tables:
        op.drop_index('idx_processed_messages_hash', table_name='processed_messages')
        op.drop_index('idx_processed_messages_agent', table_name='processed_messages')
        op.drop_table('processed_messages')
