"""add nullable company_id to lead_sources (PR 1 — schema only)

This migration adds company_id as a nullable foreign key to lead_sources.
It does NOT:
  - enforce NOT NULL
  - drop the existing global unique index on sender_email
  - add the composite unique constraint (company_id, sender_email)
  - change any query behaviour

Those changes are deferred to the next migration (PR 2), which must only
run after the backfill script has assigned every existing row to a company.

Backfill: run scripts/backfill_lead_source_company.py --company-id <id>
          before applying the PR 2 migration.

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = 'k5l6m7n8o9p0'
down_revision = 'j4k5l6m7n8o9'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add the nullable column.
    op.add_column(
        'lead_sources',
        sa.Column('company_id', sa.Integer(), nullable=True),
    )

    # 2. Add the foreign key constraint.
    op.create_foreign_key(
        'fk_lead_sources_company_id',
        source_table='lead_sources',
        referent_table='companies',
        local_cols=['company_id'],
        remote_cols=['id'],
    )

    # 3. Add a non-unique index for FK lookup performance.
    #    The global unique index on sender_email is intentionally left intact.
    op.create_index(
        'ix_lead_sources_company_id',
        'lead_sources',
        ['company_id'],
        unique=False,
    )


def downgrade():
    # Reverse in the opposite order of upgrade.
    op.drop_index('ix_lead_sources_company_id', table_name='lead_sources')
    op.drop_constraint(
        'fk_lead_sources_company_id',
        'lead_sources',
        type_='foreignkey',
    )
    op.drop_column('lead_sources', 'company_id')
