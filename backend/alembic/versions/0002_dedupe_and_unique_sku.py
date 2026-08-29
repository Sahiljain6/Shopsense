"""dedupe products and ensure unique sku

Revision ID: 0002_dedupe_and_unique_sku
Revises: 0001_add_sku
Create Date: 2026-08-29

"""
from alembic import op
import sqlalchemy as sa

revision = '0002_dedupe_and_unique_sku'
down_revision = '0001_add_sku'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()
    if "products" not in tables:
        return

    if "reviews" in tables:
        try:
            conn.execute(sa.text("""
                DELETE FROM reviews WHERE product_id IN (
                    SELECT id FROM products WHERE id NOT IN (
                        SELECT MIN(id) FROM products GROUP BY name
                    )
                )
            """))
        except Exception:
            pass

    if "wishlist" in tables:
        try:
            conn.execute(sa.text("""
                DELETE FROM wishlist WHERE product_id IN (
                    SELECT id FROM products WHERE id NOT IN (
                        SELECT MIN(id) FROM products GROUP BY name
                    )
                )
            """))
        except Exception:
            pass

    try:
        conn.execute(sa.text("""
            DELETE FROM products WHERE id NOT IN (
                SELECT MIN(id) FROM products GROUP BY name
            )
        """))
    except Exception:
        pass

    try:
        conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_products_sku ON products (sku);"))
    except Exception:
        pass

def downgrade() -> None:
    pass
