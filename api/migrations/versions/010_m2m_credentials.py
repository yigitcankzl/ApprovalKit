"""Add M2M Credential Vault fields to connections.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"


def upgrade():
    op.add_column("connections", sa.Column("m2m_api_key", sa.Text(), nullable=True))
    op.add_column("connections", sa.Column("m2m_client_id", sa.String(200), nullable=True))
    op.add_column("connections", sa.Column("m2m_token_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("connections", "m2m_token_url")
    op.drop_column("connections", "m2m_client_id")
    op.drop_column("connections", "m2m_api_key")
