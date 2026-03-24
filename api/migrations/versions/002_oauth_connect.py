"""Replace Fernet credential storage with Auth0 Token Vault OAuth connect.

Adds:
  - connected_auth0_user_id: Auth0 sub (e.g. "github|12345") of the connected service account
  - connected_user_name: display name shown in UI (e.g. "myusername")

Drops:
  - credentials_enc: Fernet-encrypted blob — no longer needed; tokens live in Auth0 Token Vault

Revision ID: 002
Revises: 001
Create Date: 2026-03-24
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("connections", sa.Column("connected_auth0_user_id", sa.String(200), nullable=True))
    op.add_column("connections", sa.Column("connected_user_name", sa.String(200), nullable=True))
    op.drop_column("connections", "credentials_enc")


def downgrade():
    op.add_column("connections", sa.Column("credentials_enc", sa.Text(), nullable=True))
    op.drop_column("connections", "connected_user_name")
    op.drop_column("connections", "connected_auth0_user_id")
