import uuid
from datetime import datetime, time

from sqlalchemy import String, DateTime, Time, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class Approver(Base):
    __tablename__ = "approvers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    auth0_user_id: Mapped[str] = mapped_column(String(200), nullable=False)
    fga_user_id: Mapped[str] = mapped_column(String(200), nullable=True)
    notify_channel: Mapped[list] = mapped_column(ARRAY(String), default=["guardian_push"])
    urgent_channel: Mapped[list] = mapped_column(ARRAY(String), default=["guardian_push", "email"])
    blackout_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    blackout_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    delegate_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approvers.id"), nullable=True)
    delegate_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delegate_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="approvers")
    delegate = relationship("Approver", remote_side="Approver.id", lazy="selectin")
