"""Add step-up authentication fields to rules.

Adds:
  - step_up_model: escalated approval model when step-up conditions are met
  - step_up_conditions: JSONB conditions that trigger step-up

Also adds 'step_up' to the audit_event enum.

Revision ID: 003
Revises: 002
Create Date: 2026-03-25
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

approval_model_enum = sa.Enum(
    "any_one", "specific", "all_of_n", "k_of_n", "sequential",
    name="approval_model", create_type=False,
)


def upgrade():
    op.add_column("rules", sa.Column("step_up_model", approval_model_enum, nullable=True))
    op.add_column("rules", sa.Column("step_up_conditions", JSONB(), nullable=True))
    op.execute("ALTER TYPE audit_event ADD VALUE IF NOT EXISTS 'step_up'")


def downgrade():
    op.drop_column("rules", "step_up_conditions")
    op.drop_column("rules", "step_up_model")
