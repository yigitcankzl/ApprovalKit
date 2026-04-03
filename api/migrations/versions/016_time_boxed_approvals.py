"""Add time-boxed approval fields: approval_expires_at, reauth columns.

Revision ID: 016
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"


def upgrade():
    # Time-boxed: computed deadline for executing an approved action
    op.add_column("approval_jobs", sa.Column("approval_expires_at", sa.DateTime(timezone=True), nullable=True))
    # Re-auth counter: how many times this agent+connection+action combo was auto-approved
    op.add_column("rules", sa.Column("reauth_every_n", sa.Integer, nullable=True))
    # Risk auto-approve threshold (may already exist from code, add only if missing)
    try:
        op.add_column("rules", sa.Column("risk_auto_approve_threshold", sa.Integer, nullable=True))
    except Exception:
        pass
    # Budget: per-rule daily/weekly/monthly spending limits (JSON)
    op.add_column("rules", sa.Column("budget_limits", sa.JSON, nullable=True))
    # Scheduled approval windows: allow approvals only in these time ranges
    op.add_column("rules", sa.Column("allowed_days", sa.JSON, nullable=True))


def downgrade():
    op.drop_column("rules", "allowed_days")
    op.drop_column("rules", "budget_limits")
    try:
        op.drop_column("rules", "risk_auto_approve_threshold")
    except Exception:
        pass
    op.drop_column("rules", "reauth_every_n")
    op.drop_column("approval_jobs", "approval_expires_at")
