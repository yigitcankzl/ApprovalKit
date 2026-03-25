"""Add auth0_refresh_token to connections for Token Exchange.

Token Vault Token Exchange requires the Auth0 refresh token to
exchange for external provider access tokens (RFC 8693).

Revision ID: 004
Revises: 003
Create Date: 2026-03-25
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("connections", sa.Column("auth0_refresh_token", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("connections", "auth0_refresh_token")
