"""add tasks table

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'k5l6m7n8o9p0'
down_revision = 'j4k5l6m7n8o9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('agent_user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('open', 'done', name='task_status_enum'), nullable=False, server_default='open'),
        sa.Column('source', sa.Enum('manual', 'pipeline', name='task_source_enum'), nullable=False, server_default='manual'),
        sa.Column('due_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_user_id'], ['agent_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tasks_lead_id', 'tasks', ['lead_id'])
    op.create_index('ix_tasks_agent_user_id', 'tasks', ['agent_user_id'])
    op.create_index('ix_tasks_status', 'tasks', ['status'])


def downgrade():
    op.drop_index('ix_tasks_status', table_name='tasks')
    op.drop_index('ix_tasks_agent_user_id', table_name='tasks')
    op.drop_index('ix_tasks_lead_id', table_name='tasks')
    op.drop_table('tasks')
    op.execute("DROP TYPE IF EXISTS task_status_enum")
    op.execute("DROP TYPE IF EXISTS task_source_enum")
