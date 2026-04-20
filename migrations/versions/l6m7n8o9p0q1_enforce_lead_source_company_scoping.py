"""enforce company_id NOT NULL and (company_id, sender_email) uniqueness on lead_sources

PR 2 — true tenant scoping for lead sources.

Prerequisites before applying this migration:
  1. Migration k5l6m7n8o9p0 must already be applied.
  2. The backfill script must have been run and verified:
       python scripts/backfill_lead_source_company.py --company-id <id> --dry-run
       python scripts/backfill_lead_source_company.py --company-id <id>
  3. Confirm zero NULL rows remain:
       SELECT COUNT(*) FROM lead_sources WHERE company_id IS NULL;
     This must return 0 before applying this migration.

What this migration does:
  - Enforces company_id NOT NULL
  - Drops the global unique index on sender_email
  - Adds composite unique constraint (company_id, sender_email)
  - Adds a non-unique index on sender_email for parser lookup performance

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = 'l6m7n8o9p0q1'
down_revision = 'k5l6m7n8o9p0'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Enforce NOT NULL — will fail if any row still has company_id IS NULL.
    #    That is intentional: the operator must run the backfill script first.
    op.alter_column(
        'lead_sources',
        'company_id',
        existing_type=sa.Integer(),
        nullable=False,
    )

    # 2. Drop the old global unique index on sender_email.
    op.drop_index('ix_lead_sources_sender_email', table_name='lead_sources')

    # 3. Add composite unique constraint — two companies may share a sender_email,
    #    but one company may not have two rules for the same sender.
    op.create_unique_constraint(
        'uq_lead_sources_company_sender',
        'lead_sources',
        ['company_id', 'sender_email'],
    )

    # 4. Re-add sender_email as a non-unique index for parser lookup performance.
    op.create_index(
        'ix_lead_sources_sender_email',
        'lead_sources',
        ['sender_email'],
        unique=False,
    )


def downgrade():
    # Reverse in opposite order.
    op.drop_index('ix_lead_sources_sender_email', table_name='lead_sources')
    op.drop_constraint('uq_lead_sources_company_sender', 'lead_sources', type_='unique')

    # Restore the original global unique index.
    op.create_index(
        'ix_lead_sources_sender_email',
        'lead_sources',
        ['sender_email'],
        unique=True,
    )

    op.alter_column(
        'lead_sources',
        'company_id',
        existing_type=sa.Integer(),
        nullable=True,
    )
