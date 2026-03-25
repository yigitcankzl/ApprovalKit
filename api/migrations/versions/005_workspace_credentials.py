"""Add Auth0/FGA credential columns to workspaces for multi-tenant config.

Each workspace stores its own Auth0 and FGA credentials in the database,
eliminating the need for .env configuration per organization.

Revision ID: 005
Revises: 004
Create Date: 2026-03-25
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("workspaces", sa.Column("auth0_domain", sa.String(200), nullable=True))
    op.add_column("workspaces", sa.Column("auth0_m2m_client_id", sa.String(200), nullable=True))
    op.add_column("workspaces", sa.Column("auth0_m2m_client_secret", sa.Text(), nullable=True))
    op.add_column("workspaces", sa.Column("auth0_web_client_id", sa.String(200), nullable=True))
    op.add_column("workspaces", sa.Column("auth0_web_client_secret", sa.Text(), nullable=True))
    op.add_column("workspaces", sa.Column("auth0_audience", sa.String(300), nullable=True))
    op.add_column("workspaces", sa.Column("auth0_mgmt_api_audience", sa.String(300), nullable=True))
    op.add_column("workspaces", sa.Column("fga_api_url", sa.String(300), nullable=True))
    op.add_column("workspaces", sa.Column("fga_store_id", sa.String(100), nullable=True))
    op.add_column("workspaces", sa.Column("fga_model_id", sa.String(100), nullable=True))
    op.add_column("workspaces", sa.Column("fga_client_id", sa.String(200), nullable=True))
    op.add_column("workspaces", sa.Column("fga_client_secret", sa.Text(), nullable=True))
    op.add_column("workspaces", sa.Column("credentials_key", sa.Text(), nullable=True))
    op.add_column("workspaces", sa.Column("owner_auth0_sub", sa.String(200), nullable=True))


def downgrade():
    op.drop_column("workspaces", "owner_auth0_sub")
    op.drop_column("workspaces", "credentials_key")
    op.drop_column("workspaces", "fga_client_secret")
    op.drop_column("workspaces", "fga_client_id")
    op.drop_column("workspaces", "fga_model_id")
    op.drop_column("workspaces", "fga_store_id")
    op.drop_column("workspaces", "fga_api_url")
    op.drop_column("workspaces", "auth0_mgmt_api_audience")
    op.drop_column("workspaces", "auth0_audience")
    op.drop_column("workspaces", "auth0_web_client_secret")
    op.drop_column("workspaces", "auth0_web_client_id")
    op.drop_column("workspaces", "auth0_m2m_client_secret")
    op.drop_column("workspaces", "auth0_m2m_client_id")
    op.drop_column("workspaces", "auth0_domain")
