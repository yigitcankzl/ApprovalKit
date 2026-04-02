"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types via raw SQL (asyncpg checkfirst is unreliable)
    op.execute("DO $$ BEGIN CREATE TYPE approval_model AS ENUM ('any_one', 'specific', 'all_of_n', 'k_of_n', 'sequential'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE timeout_action AS ENUM ('block', 'escalate'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE job_state AS ENUM ('pending', 'ciba_sent', 'waiting_approval', 'partially_approved', 'approved', 'rejected', 'timeout', 'escalated', 'blocked', 'pre_approved'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE audit_event AS ENUM ('requested', 'ciba_sent', 'approved', 'rejected', 'timeout', 'escalated', 'blocked', 'pre_approved', 'partial_approved', 'scope_creep', 'revoked'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # Reference enums without auto-creating them
    approval_model = sa.Enum("any_one", "specific", "all_of_n", "k_of_n", "sequential", name="approval_model", create_type=False)
    timeout_action = sa.Enum("block", "escalate", name="timeout_action", create_type=False)
    job_state = sa.Enum(
        "pending", "ciba_sent", "waiting_approval", "partially_approved",
        "approved", "rejected", "timeout", "escalated", "blocked", "pre_approved",
        name="job_state", create_type=False,
    )
    audit_event = sa.Enum(
        "requested", "ciba_sent", "approved", "rejected", "timeout",
        "escalated", "blocked", "pre_approved", "partial_approved",
        "scope_creep", "revoked",
        name="audit_event", create_type=False,
    )

    # Workspaces
    op.create_table(
        "workspaces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("auth0_tenant", sa.String(200), nullable=False),
        sa.Column("api_key", sa.String(64), unique=True, nullable=False),
        sa.Column("hmac_secret", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Connections
    op.create_table(
        "connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("service", sa.String(100), nullable=False),
        sa.Column("token_vault_connection_id", sa.String(200), nullable=False),
        sa.Column("actions", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Approvers
    op.create_table(
        "approvers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("auth0_user_id", sa.String(200), nullable=False),
        sa.Column("fga_user_id", sa.String(200), nullable=True),
        sa.Column("notify_channel", ARRAY(sa.String), server_default="{guardian_push}"),
        sa.Column("urgent_channel", ARRAY(sa.String), server_default="{guardian_push,email}"),
        sa.Column("blackout_start", sa.Time, nullable=True),
        sa.Column("blackout_end", sa.Time, nullable=True),
        sa.Column("delegate_to", UUID(as_uuid=True), sa.ForeignKey("approvers.id"), nullable=True),
        sa.Column("delegate_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delegate_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Rules
    op.create_table(
        "rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("connection", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("conditions", JSONB, server_default="[]"),
        sa.Column("model", approval_model, nullable=False),
        sa.Column("k_value", sa.Integer, nullable=True),
        sa.Column("timeout_seconds", sa.Integer, default=300),
        sa.Column("on_timeout", timeout_action, server_default="block"),
        sa.Column("escalate_to", UUID(as_uuid=True), sa.ForeignKey("approvers.id"), nullable=True),
        sa.Column("cooldown_max", sa.Integer, nullable=True),
        sa.Column("blackout_start", sa.Time, nullable=True),
        sa.Column("blackout_end", sa.Time, nullable=True),
        sa.Column("pre_approval", JSONB, nullable=True),
        sa.Column("context_template", sa.Text, nullable=True),
        sa.Column("partial_approval", sa.Boolean, default=False),
        sa.Column("quorum_window", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("priority", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Rule-Approver join table
    op.create_table(
        "rule_approvers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_id", UUID(as_uuid=True), sa.ForeignKey("rules.id"), nullable=False),
        sa.Column("approver_id", UUID(as_uuid=True), sa.ForeignKey("approvers.id"), nullable=False),
        sa.Column("order", sa.Integer, default=0),
    )

    # Approval Jobs
    op.create_table(
        "approval_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("idempotency_key", sa.String(200), unique=True, nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("rule_id", UUID(as_uuid=True), sa.ForeignKey("rules.id"), nullable=False),
        sa.Column("connection", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("params", JSONB, nullable=False),
        sa.Column("agent_user_id", sa.String(200), nullable=False),
        sa.Column("state", job_state, server_default="pending"),
        sa.Column("approvals_count", sa.Integer, default=0),
        sa.Column("required_count", sa.Integer, nullable=False, default=1),
        sa.Column("escalated_to", UUID(as_uuid=True), sa.ForeignKey("approvers.id"), nullable=True),
        sa.Column("final_params", JSONB, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Audit Log
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("approval_jobs.id"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("approver_id", UUID(as_uuid=True), sa.ForeignKey("approvers.id"), nullable=True),
        sa.Column("event_type", audit_event, nullable=False),
        sa.Column("binding_message", sa.Text, nullable=True),
        sa.Column("modified_params", JSONB, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Indexes
    op.create_index("ix_approval_jobs_idempotency", "approval_jobs", ["idempotency_key"], unique=True)
    op.create_index("ix_approval_jobs_workspace", "approval_jobs", ["workspace_id"])
    op.create_index("ix_approval_jobs_state", "approval_jobs", ["state"])
    op.create_index("ix_audit_log_job", "audit_log", ["job_id"])
    op.create_index("ix_audit_log_workspace", "audit_log", ["workspace_id"])
    op.create_index("ix_rules_workspace_action", "rules", ["workspace_id", "connection", "action"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("approval_jobs")
    op.drop_table("rule_approvers")
    op.drop_table("rules")
    op.drop_table("approvers")
    op.drop_table("connections")
    op.drop_table("workspaces")

    op.execute("DROP TYPE IF EXISTS audit_event")
    op.execute("DROP TYPE IF EXISTS job_state")
    op.execute("DROP TYPE IF EXISTS timeout_action")
    op.execute("DROP TYPE IF EXISTS approval_model")
