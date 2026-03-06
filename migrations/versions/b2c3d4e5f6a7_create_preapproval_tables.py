"""create_preapproval_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Form System ---

    op.create_table(
        'form_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('intent_type', sa.String(length=10), nullable=False, server_default='BUY'),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_form_templates_tenant_id', 'form_templates', ['tenant_id'])

    op.create_table(
        'form_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('schema_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['form_templates.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_form_versions_template_id', 'form_versions', ['template_id'])

    op.create_table(
        'form_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('form_version_id', sa.Integer(), nullable=False),
        sa.Column('question_key', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('label', sa.String(length=500), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=True),
        sa.Column('options_json', sa.Text(), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('validation_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['form_version_id'], ['form_versions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_form_questions_form_version_id', 'form_questions', ['form_version_id'])

    op.create_table(
        'form_logic_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('form_version_id', sa.Integer(), nullable=False),
        sa.Column('rule_json', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['form_version_id'], ['form_versions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_form_logic_rules_form_version_id', 'form_logic_rules', ['form_version_id'])

    # --- Scoring System ---

    op.create_table(
        'scoring_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('intent_type', sa.String(length=10), nullable=False, server_default='BUY'),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scoring_configs_tenant_id', 'scoring_configs', ['tenant_id'])

    op.create_table(
        'scoring_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scoring_config_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('rules_json', sa.Text(), nullable=False),
        sa.Column('thresholds_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['scoring_config_id'], ['scoring_configs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scoring_versions_scoring_config_id', 'scoring_versions', ['scoring_config_id'])

    # --- Invitations & Submissions ---

    op.create_table(
        'form_invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('intent_type', sa.String(length=10), nullable=False, server_default='BUY'),
        sa.Column('form_version_id', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('channel', sa.String(length=20), nullable=False, server_default='email'),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['form_version_id'], ['form_versions.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_form_invitations_token_hash'),
    )
    op.create_index('ix_form_invitations_tenant_id', 'form_invitations', ['tenant_id'])
    op.create_index('ix_form_invitations_lead_id', 'form_invitations', ['lead_id'])
    op.create_index('ix_form_invitations_token_hash', 'form_invitations', ['token_hash'], unique=True)

    op.create_table(
        'form_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('intent_type', sa.String(length=10), nullable=False, server_default='BUY'),
        sa.Column('form_version_id', sa.Integer(), nullable=False),
        sa.Column('scoring_version_id', sa.Integer(), nullable=True),
        sa.Column('invitation_id', sa.Integer(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('device_type', sa.String(length=50), nullable=True),
        sa.Column('time_to_submit_seconds', sa.Integer(), nullable=True),
        sa.Column('lead_source', sa.String(length=255), nullable=True),
        sa.Column('property_address', sa.String(length=500), nullable=True),
        sa.Column('listing_url', sa.String(length=1000), nullable=True),
        sa.Column('repeat_inquiry_count', sa.Integer(), nullable=True),
        sa.Column('raw_payload_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['form_version_id'], ['form_versions.id']),
        sa.ForeignKeyConstraint(['invitation_id'], ['form_invitations.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.ForeignKeyConstraint(['scoring_version_id'], ['scoring_versions.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_form_submissions_tenant_id', 'form_submissions', ['tenant_id'])
    op.create_index('ix_form_submissions_lead_id', 'form_submissions', ['lead_id'])

    op.create_table(
        'submission_answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('question_key', sa.String(length=100), nullable=False),
        sa.Column('answer_value_json', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['form_submissions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_submission_answers_submission_id', 'submission_answers', ['submission_id'])

    op.create_table(
        'submission_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('total_score', sa.Integer(), nullable=False),
        sa.Column('bucket', sa.String(length=20), nullable=False),
        sa.Column('breakdown_json', sa.Text(), nullable=False),
        sa.Column('explanation_text', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['form_submissions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('submission_id', name='uq_submission_scores_submission_id'),
    )

    # --- Message Templates ---

    op.create_table(
        'message_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('intent_type', sa.String(length=10), nullable=False, server_default='BUY'),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_message_templates_tenant_id', 'message_templates', ['tenant_id'])

    op.create_table(
        'message_template_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('subject_template', sa.String(length=500), nullable=False),
        sa.Column('body_template', sa.Text(), nullable=False),
        sa.Column('variants_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['message_templates.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_message_template_versions_template_id', 'message_template_versions', ['template_id'])

    # --- Lead State Machine ---

    op.create_table(
        'lead_state_transitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('intent_type', sa.String(length=10), nullable=False, server_default='BUY'),
        sa.Column('from_state', sa.String(length=50), nullable=True),
        sa.Column('to_state', sa.String(length=50), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('actor_type', sa.String(length=20), nullable=False, server_default='system'),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lead_state_transitions_tenant_id', 'lead_state_transitions', ['tenant_id'])
    op.create_index('ix_lead_state_transitions_lead_id', 'lead_state_transitions', ['lead_id'])
    op.create_index('ix_lead_state_transitions_occurred_at', 'lead_state_transitions', ['occurred_at'])
    op.create_index('ix_lead_state_transitions_lead_id_occurred_at', 'lead_state_transitions', ['lead_id', 'occurred_at'])

    op.create_table(
        'lead_interactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('intent_type', sa.String(length=10), nullable=False, server_default='BUY'),
        sa.Column('channel', sa.String(length=20), nullable=False, server_default='email'),
        sa.Column('direction', sa.String(length=10), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lead_interactions_tenant_id', 'lead_interactions', ['tenant_id'])
    op.create_index('ix_lead_interactions_lead_id', 'lead_interactions', ['lead_id'])
    op.create_index('ix_lead_interactions_occurred_at', 'lead_interactions', ['occurred_at'])


def downgrade() -> None:
    op.drop_index('ix_lead_interactions_occurred_at', table_name='lead_interactions')
    op.drop_index('ix_lead_interactions_lead_id', table_name='lead_interactions')
    op.drop_index('ix_lead_interactions_tenant_id', table_name='lead_interactions')
    op.drop_table('lead_interactions')

    op.drop_index('ix_lead_state_transitions_lead_id_occurred_at', table_name='lead_state_transitions')
    op.drop_index('ix_lead_state_transitions_occurred_at', table_name='lead_state_transitions')
    op.drop_index('ix_lead_state_transitions_lead_id', table_name='lead_state_transitions')
    op.drop_index('ix_lead_state_transitions_tenant_id', table_name='lead_state_transitions')
    op.drop_table('lead_state_transitions')

    op.drop_index('ix_message_template_versions_template_id', table_name='message_template_versions')
    op.drop_table('message_template_versions')

    op.drop_index('ix_message_templates_tenant_id', table_name='message_templates')
    op.drop_table('message_templates')

    op.drop_table('submission_scores')

    op.drop_index('ix_submission_answers_submission_id', table_name='submission_answers')
    op.drop_table('submission_answers')

    op.drop_index('ix_form_submissions_lead_id', table_name='form_submissions')
    op.drop_index('ix_form_submissions_tenant_id', table_name='form_submissions')
    op.drop_table('form_submissions')

    op.drop_index('ix_form_invitations_token_hash', table_name='form_invitations')
    op.drop_index('ix_form_invitations_lead_id', table_name='form_invitations')
    op.drop_index('ix_form_invitations_tenant_id', table_name='form_invitations')
    op.drop_table('form_invitations')

    op.drop_index('ix_scoring_versions_scoring_config_id', table_name='scoring_versions')
    op.drop_table('scoring_versions')

    op.drop_index('ix_scoring_configs_tenant_id', table_name='scoring_configs')
    op.drop_table('scoring_configs')

    op.drop_index('ix_form_logic_rules_form_version_id', table_name='form_logic_rules')
    op.drop_table('form_logic_rules')

    op.drop_index('ix_form_questions_form_version_id', table_name='form_questions')
    op.drop_table('form_questions')

    op.drop_index('ix_form_versions_template_id', table_name='form_versions')
    op.drop_table('form_versions')

    op.drop_index('ix_form_templates_tenant_id', table_name='form_templates')
    op.drop_table('form_templates')
