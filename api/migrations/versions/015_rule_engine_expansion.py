"""Add max_requests_per_hour, approval_expiry_seconds, trigger_rules columns to rules.

Revision ID: 015
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "015"
down_revision = "014"


def upgrade():
    op.add_column("rules", sa.Column("max_requests_per_hour", sa.Integer, nullable=True))
    op.add_column("rules", sa.Column("approval_expiry_seconds", sa.Integer, nullable=True))
    op.add_column("rules", sa.Column("trigger_rules", JSONB, nullable=True))


def downgrade():
    op.drop_column("rules", "trigger_rules")
    op.drop_column("rules", "approval_expiry_seconds")
    op.drop_column("rules", "max_requests_per_hour")
