"""initial schema
Revision ID: 0001_initial
Revises:
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial"; down_revision = None; branch_labels = None; depends_on = None
def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(255), unique=True), sa.Column("hashed_password", sa.String(255)), sa.Column("full_name", sa.String(120)), sa.Column("is_admin", sa.Boolean(), default=False), sa.Column("created_at", sa.DateTime()))
    op.create_table("categories", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), unique=True), sa.Column("slug", sa.String(140), unique=True))
    op.create_table("products", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id")), sa.Column("name", sa.String(200)), sa.Column("brand", sa.String(120)), sa.Column("description", sa.Text()), sa.Column("price", sa.Float()), sa.Column("currency", sa.String(8)), sa.Column("rating", sa.Float()), sa.Column("stock", sa.Integer()), sa.Column("image_url", sa.String(500)), sa.Column("attributes", sa.JSON()))
    op.create_table("reviews", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True), sa.Column("rating", sa.Float()), sa.Column("title", sa.String(200)), sa.Column("body", sa.Text()), sa.Column("sentiment", sa.String(40)))
    op.create_table("orders", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("status", sa.String(40)), sa.Column("total", sa.Float()))
    op.create_table("chat_history", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("role", sa.String(20)), sa.Column("content", sa.Text()), sa.Column("memory", sa.JSON()), sa.Column("created_at", sa.DateTime()))
    op.create_table("wishlist", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")))
    op.create_table("saved_recommendations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("product_ids", sa.JSON()), sa.Column("rationale", sa.Text()))
def downgrade():
    for t in ["saved_recommendations","wishlist","chat_history","orders","reviews","products","categories","users"]: op.drop_table(t)
