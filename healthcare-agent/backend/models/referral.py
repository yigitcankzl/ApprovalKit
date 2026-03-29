import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referral_type: Mapped[str] = mapped_column(String(30))
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"))
    referring_doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"))
    external_entity_name: Mapped[str] = mapped_column(String(200))
    external_entity_email: Mapped[str] = mapped_column(String(320))
    reason: Mapped[str] = mapped_column(Text)
    data_scope: Mapped[str] = mapped_column(String(20), default="summary")
    final_data_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    shared_files: Mapped[list] = mapped_column(JSONB, default=list)
    shared_drive_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    patient_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="pending_approval")
    approval_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    audit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", lazy="selectin")
    referring_doctor = relationship("Doctor", foreign_keys=[referring_doctor_id], lazy="selectin")
