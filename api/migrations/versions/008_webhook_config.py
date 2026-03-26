"""Add webhook config columns to connections for generic API execution.

Revision ID: 008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "008"
down_revision = "007"


def upgrade():
    op.add_column("connections", sa.Column("webhook_url", sa.Text(), nullable=True))
    op.add_column("connections", sa.Column("webhook_method", sa.String(10), nullable=True))
    op.add_column("connections", sa.Column("webhook_headers", JSONB(), nullable=True))
    op.add_column("connections", sa.Column("webhook_body_template", JSONB(), nullable=True))


def downgrade():
    op.drop_column("connections", "webhook_body_template")
    op.drop_column("connections", "webhook_headers")
    op.drop_column("connections", "webhook_method")
    op.drop_column("connections", "webhook_url")
