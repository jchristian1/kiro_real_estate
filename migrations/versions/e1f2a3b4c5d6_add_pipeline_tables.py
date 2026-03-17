"""add_pipeline_tables

Revision ID: e1f2a3b4c5d6
Revises: f3a4b5c6d7e8
Create Date: 2026-06-01 00:00:00.000000

Requirements: 13.1, 13.2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- pipelines ---
    op.create_table(
        'pipelines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'name', name='uq_pipeline_company_name'),
    )
    op.create_index('ix_pipelines_company_id', 'pipelines', ['company_id'])

    # --- pipeline_stages ---
    op.create_table(
        'pipeline_stages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pipeline_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=False),
        sa.Column('category', sa.Enum('open', 'in_progress', 'waiting', 'won', 'lost', name='stagecategory'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('is_closed_won', sa.Boolean(), nullable=False),
        sa.Column('is_closed_lost', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pipeline_id', 'key', name='uq_pipeline_stage_key'),
    )
    op.create_index('ix_pipeline_stages_pipeline_id', 'pipeline_stages', ['pipeline_id'])

    # --- lead_stage_history ---
    op.create_table(
        'lead_stage_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('from_stage_id', sa.Integer(), nullable=True),
        sa.Column('to_stage_id', sa.Integer(), nullable=False),
        sa.Column('change_source', sa.Enum('system', 'event', 'automation', 'manual', name='changesource'), nullable=False),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['from_stage_id'], ['pipeline_stages.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.ForeignKeyConstraint(['to_stage_id'], ['pipeline_stages.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_lead_stage_history_lead_created', 'lead_stage_history', ['lead_id', 'created_at'])

    # --- pipeline_event_mappings ---
    op.create_table(
        'pipeline_event_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pipeline_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.Enum(
            'lead_created', 'response_email_sent', 'qualification_form_sent',
            'qualification_form_submitted', 'qualification_bucket_hot',
            'qualification_bucket_warm', 'qualification_bucket_nurture',
            name='builtineventtype',
        ), nullable=False),
        sa.Column('target_stage_id', sa.Integer(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id']),
        sa.ForeignKeyConstraint(['target_stage_id'], ['pipeline_stages.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pipeline_id', 'event_type', name='uq_pipeline_event_mapping'),
    )
    op.create_index('ix_pipeline_event_mappings_pipeline_id', 'pipeline_event_mappings', ['pipeline_id'])

    # --- pipeline_action_rules ---
    op.create_table(
        'pipeline_action_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pipeline_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('trigger_type', sa.String(length=50), nullable=False),
        sa.Column('trigger_stage_id', sa.Integer(), nullable=True),
        sa.Column('trigger_event_type', sa.String(length=100), nullable=True),
        sa.Column('condition_type', sa.String(length=50), nullable=False),
        sa.Column('condition_value', sa.String(length=255), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id']),
        sa.ForeignKeyConstraint(['trigger_stage_id'], ['pipeline_stages.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pipeline_action_rules_pipeline_id', 'pipeline_action_rules', ['pipeline_id'])

    # --- pipeline_action_rule_steps ---
    op.create_table(
        'pipeline_action_rule_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.Enum(
            'send_email_template', 'send_qualification_form',
            'send_bucket_followup_email', 'move_to_stage',
            name='actiontype',
        ), nullable=False),
        sa.Column('action_config_json', sa.Text(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['pipeline_action_rules.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pipeline_action_rule_steps_rule_id', 'pipeline_action_rule_steps', ['rule_id'])

    # --- new columns on leads ---
    with op.batch_alter_table('leads') as batch_op:
        batch_op.add_column(sa.Column('pipeline_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('current_stage_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('stage_entered_at', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key('fk_leads_pipeline_id', 'pipelines', ['pipeline_id'], ['id'])
        batch_op.create_foreign_key('fk_leads_current_stage_id', 'pipeline_stages', ['current_stage_id'], ['id'])
        batch_op.create_index('ix_leads_pipeline_id', ['pipeline_id'])
        batch_op.create_index('ix_leads_current_stage_id', ['current_stage_id'])


def downgrade() -> None:
    # Remove new columns from leads first
    with op.batch_alter_table('leads') as batch_op:
        batch_op.drop_index('ix_leads_current_stage_id')
        batch_op.drop_index('ix_leads_pipeline_id')
        batch_op.drop_constraint('fk_leads_current_stage_id', type_='foreignkey')
        batch_op.drop_constraint('fk_leads_pipeline_id', type_='foreignkey')
        batch_op.drop_column('stage_entered_at')
        batch_op.drop_column('current_stage_id')
        batch_op.drop_column('pipeline_id')

    # Drop tables in reverse FK dependency order
    op.drop_index('ix_pipeline_action_rule_steps_rule_id', table_name='pipeline_action_rule_steps')
    op.drop_table('pipeline_action_rule_steps')

    op.drop_index('ix_pipeline_action_rules_pipeline_id', table_name='pipeline_action_rules')
    op.drop_table('pipeline_action_rules')

    op.drop_index('ix_pipeline_event_mappings_pipeline_id', table_name='pipeline_event_mappings')
    op.drop_table('pipeline_event_mappings')

    op.drop_index('idx_lead_stage_history_lead_created', table_name='lead_stage_history')
    op.drop_table('lead_stage_history')

    op.drop_index('ix_pipeline_stages_pipeline_id', table_name='pipeline_stages')
    op.drop_table('pipeline_stages')

    op.drop_index('ix_pipelines_company_id', table_name='pipelines')
    op.drop_table('pipelines')

    # Drop enum types (needed for PostgreSQL; no-op on SQLite)
    sa.Enum(name='actiontype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='builtineventtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='changesource').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='stagecategory').drop(op.get_bind(), checkfirst=True)
