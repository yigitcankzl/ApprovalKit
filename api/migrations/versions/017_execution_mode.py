"""Add execution_mode to approval_jobs (client vs server execution).

Revision ID: 017
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"


def upgrade():
    # "server" default preserves legacy behavior for existing rows and for
    # REST callers that omit the field.
    op.add_column(
        "approval_jobs",
        sa.Column(
            "execution_mode",
            sa.String(length=10),
            nullable=False,
            server_default="server",
        ),
    )


def downgrade():
    op.drop_column("approval_jobs", "execution_mode")
