"""add_companies_table_and_company_id_to_credentials

Revision ID: ed911637cb7a
Revises: ee5ff1fa8ad2
Create Date: 2026-03-03 22:05:55.532617

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed911637cb7a'
down_revision: Union[str, Sequence[str], None] = 'ee5ff1fa8ad2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'companies' not in existing_tables:
        op.create_table(
            'companies',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('phone', sa.String(length=50), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    # Add company_id to credentials if not already present
    existing_cols = [c['name'] for c in inspector.get_columns('credentials')]
    if 'company_id' not in existing_cols:
        op.add_column('credentials', sa.Column('company_id', sa.Integer(), nullable=True))

    # Add company_id to users if not already present
    users_cols = [c['name'] for c in inspector.get_columns('users')]
    if 'company_id' not in users_cols:
        op.add_column('users', sa.Column('company_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema — reverses only what upgrade() actually does."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop company_id from credentials if present
    cred_cols = [c['name'] for c in inspector.get_columns('credentials')]
    if 'company_id' in cred_cols:
        op.drop_column('credentials', 'company_id')

    # Drop company_id from users if present
    users_cols = [c['name'] for c in inspector.get_columns('users')]
    if 'company_id' in users_cols:
        op.drop_column('users', 'company_id')

    # Drop companies table if present
    existing_tables = inspector.get_table_names()
    if 'companies' in existing_tables:
        op.drop_table('companies')
