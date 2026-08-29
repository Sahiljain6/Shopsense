"""add sku to products

Revision ID: 0001_add_sku
Revises: 
Create Date: 2026-08-29

"""
from alembic import op
import sqlalchemy as sa

revision = '0001_add_sku'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("ALTER TABLE products ADD COLUMN IF NOT EXISTS sku VARCHAR(120);"))
        conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_products_sku ON products (sku);"))
    elif conn.dialect.name == "sqlite":
        cols = [r[1] for r in conn.execute(sa.text("PRAGMA table_info(products)")).fetchall()]
        if cols and "sku" not in cols:
            with op.batch_alter_table('products') as batch_op:
                batch_op.add_column(sa.Column('sku', sa.String(120), nullable=True))
                batch_op.create_index('ix_products_sku', ['sku'], unique=True)
    else:
        try:
            op.add_column('products', sa.Column('sku', sa.String(120), nullable=True))
            op.create_index('ix_products_sku', 'products', ['sku'], unique=True)
        except Exception:
            pass

def downgrade() -> None:
    try:
        op.drop_index('ix_products_sku', table_name='products')
        op.drop_column('products', 'sku')
    except Exception:
        pass
