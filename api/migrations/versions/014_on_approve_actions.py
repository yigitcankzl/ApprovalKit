"""Add on_approve_actions JSONB column to rules.

After approval, Token Vault executes these additional actions
(e.g. send Gmail, post Slack message, create Calendar event).

Revision ID: 014
Revises: 013
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "014"
down_revision = "013"


def upgrade():
    op.add_column("rules", sa.Column("on_approve_actions", JSONB, nullable=True))


def downgrade():
    op.drop_column("rules", "on_approve_actions")
