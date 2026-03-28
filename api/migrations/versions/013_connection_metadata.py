"""Add metadata JSONB column to connections.

Revision ID: 013
Revises: 012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "013"
down_revision = "012"


def upgrade():
    op.add_column("connections", sa.Column("config_meta", JSONB, nullable=True))


def downgrade():
    op.drop_column("connections", "config_meta")
