"""Add approval_checklist to rules for structured approver verification.

Revision ID: 009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "009"
down_revision = "008"


def upgrade():
    op.add_column("rules", sa.Column("approval_checklist", JSONB(), nullable=True))


def downgrade():
    op.drop_column("rules", "approval_checklist")
