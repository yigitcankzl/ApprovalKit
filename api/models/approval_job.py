import enum
import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class JobState(str, enum.Enum):
    PENDING = "pending"
    CIBA_SENT = "ciba_sent"
    WAITING_APPROVAL = "waiting_approval"
    PARTIALLY_APPROVED = "partially_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ESCALATED = "escalated"
    BLOCKED = "blocked"
    PRE_APPROVED = "pre_approved"


class AuditEventType(str, enum.Enum):
    REQUESTED = "requested"
    CIBA_SENT = "ciba_sent"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ESCALATED = "escalated"
    BLOCKED = "blocked"
    PRE_APPROVED = "pre_approved"
    PARTIAL_APPROVED = "partial_approved"
    SCOPE_CREEP = "scope_creep"
    REVOKED = "revoked"
    STEP_UP = "step_up"


class ApprovalJob(Base):
    __tablename__ = "approval_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rules.id"), nullable=False)
    connection: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    agent_user_id: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[JobState] = mapped_column(Enum(JobState, name="job_state", values_callable=lambda x: [e.value for e in x]), default=JobState.PENDING)
    approvals_count: Mapped[int] = mapped_column(Integer, default=0)
    required_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    escalated_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approvers.id"), nullable=True)
    final_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    rule = relationship("Rule", lazy="selectin")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("approval_jobs.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approvers.id"), nullable=True)
    event_type: Mapped[AuditEventType] = mapped_column(Enum(AuditEventType, name="audit_event", values_callable=lambda x: [e.value for e in x]), nullable=False)
    binding_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    job = relationship("ApprovalJob", lazy="selectin")
    approver = relationship("Approver", lazy="selectin")
