"""Add encrypted AI API key column to workspaces.

Revision ID: 012
Revises: 011
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"


def upgrade():
    op.add_column("workspaces", sa.Column("ai_api_key_encrypted", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("workspaces", "ai_api_key_encrypted")
