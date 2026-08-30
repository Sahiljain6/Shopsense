"""add google_id, nullable password

Revision ID: 8d97f4f38bae
Revises: 0002_dedupe_and_unique_sku
Create Date: 2026-08-30 21:07:26.028358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_add_google_id_nullable_password'
down_revision: Union[str, None] = '0002_dedupe_and_unique_sku'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
        op.alter_column('users', 'hashed_password',
                   existing_type=sa.VARCHAR(length=255),
                   nullable=True)
        op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)
    else:
        # SQLite dialect
        insp = sa.inspect(conn)
        cols = [c["name"] for c in insp.get_columns("users")]
        if "google_id" not in cols:
            op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
            op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        op.drop_index('ix_users_google_id', table_name='users')
        op.alter_column('users', 'hashed_password',
                   existing_type=sa.VARCHAR(length=255),
                   nullable=False)
        op.drop_column('users', 'google_id')
    else:
        try:
            op.drop_index('ix_users_google_id', table_name='users')
            op.drop_column('users', 'google_id')
        except Exception:
            pass
