"""Add per-agent API keys and allowed_connections.

Each agent gets its own API key for identity tracking and revocation.
allowed_connections restricts which services an agent can access.

Revision ID: 007
Revises: 006
Create Date: 2026-03-26
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("registered_agents", sa.Column("api_key", sa.String(64), unique=True, nullable=True))
    op.add_column("registered_agents", sa.Column("allowed_connections", JSONB(), nullable=True))
    op.add_column("registered_agents", sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"))


def downgrade():
    op.drop_column("registered_agents", "is_active")
    op.drop_column("registered_agents", "allowed_connections")
    op.drop_column("registered_agents", "api_key")
