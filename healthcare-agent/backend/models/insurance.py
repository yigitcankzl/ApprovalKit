import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class InsuranceProvider(Base):
    __tablename__ = "insurance_providers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    plan_type: Mapped[str] = mapped_column(String(50))
    contact_email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(20))
    coverage_details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InsuranceRequest(Base):
    __tablename__ = "insurance_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"))
    insurance_provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_providers.id")
    )
    request_type: Mapped[str] = mapped_column(String(30))
    requested_data_scope: Mapped[str] = mapped_column(String(20), default="summary")
    final_data_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending_approval")
    approval_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", lazy="selectin")
    insurance_provider = relationship("InsuranceProvider", lazy="selectin")
