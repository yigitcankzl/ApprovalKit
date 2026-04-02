import enum
import uuid
from datetime import datetime, time

from sqlalchemy import String, Integer, Boolean, DateTime, Time, Text, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class ApprovalModel(str, enum.Enum):
    ANY_ONE = "any_one"
    SPECIFIC = "specific"
    ALL_OF_N = "all_of_n"
    K_OF_N = "k_of_n"
    SEQUENTIAL = "sequential"
    FGA_DYNAMIC = "fga_dynamic"


class TimeoutAction(str, enum.Enum):
    BLOCK = "block"
    ESCALATE = "escalate"


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    connection: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSONB, default=list)
    model: Mapped[ApprovalModel] = mapped_column(Enum(ApprovalModel, name="approval_model", values_callable=lambda x: [e.value for e in x]), nullable=False)
    k_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    on_timeout: Mapped[TimeoutAction] = mapped_column(Enum(TimeoutAction, name="timeout_action", values_callable=lambda x: [e.value for e in x]), default=TimeoutAction.BLOCK)
    escalate_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approvers.id"), nullable=True)
    cooldown_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blackout_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    blackout_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    pre_approval: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    context_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    partial_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    quorum_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_up_model: Mapped[ApprovalModel | None] = mapped_column(
        Enum(ApprovalModel, name="approval_model", values_callable=lambda x: [e.value for e in x], create_constraint=False),
        nullable=True,
    )
    step_up_conditions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Structured checklist items the approver must confirm before approving
    # e.g. [{"id": "amount", "label": "I verified the charge amount"}, ...]
    approval_checklist: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Actions to execute via Token Vault after approval
    # e.g. [{"connection": "gmail-prod", "action": "send_email", "params": {"to": "...", "subject": "..."}}]
    on_approve_actions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Agent rate limiting: max requests per hour for this connection (0 = unlimited)
    max_requests_per_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Approval expiry: approved decisions expire if not executed within N seconds
    approval_expiry_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Rule chaining: trigger additional rules after this one is approved
    # e.g. [{"connection": "gmail-prod", "action": "send_email", "params": {"subject": "Invoice for {{amount}}"}}]
    trigger_rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Feature 7: auto-approve if risk_score <= this threshold (None = disabled)
    risk_auto_approve_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="rules")
    escalate_approver = relationship("Approver", foreign_keys=[escalate_to], lazy="selectin")
    rule_approvers = relationship("RuleApprover", back_populates="rule", lazy="selectin")


class RuleApprover(Base):
    __tablename__ = "rule_approvers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rules.id"), nullable=False)
    approver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("approvers.id"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    rule = relationship("Rule", back_populates="rule_approvers")
    approver = relationship("Approver", lazy="selectin")
