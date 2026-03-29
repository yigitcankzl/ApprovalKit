import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rx_number: Mapped[str] = mapped_column(String(20), unique=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"))
    prescribing_doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"))
    medication_name: Mapped[str] = mapped_column(String(200))
    medication_code: Mapped[str] = mapped_column(String(20))
    dosage: Mapped[str] = mapped_column(String(100))
    frequency: Mapped[str] = mapped_column(String(100), default="once daily")
    quantity: Mapped[int] = mapped_column(Integer)
    refills: Mapped[int] = mapped_column(Integer, default=0)
    is_controlled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_class: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_approval")
    approval_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by_doctor: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by_pharmacist: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by_cmo: Mapped[bool] = mapped_column(Boolean, default=False)
    pharmacy_email: Mapped[str] = mapped_column(String(320), default="pharmacy@medcore-hospital.com")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="prescriptions", lazy="selectin")
    prescribing_doctor = relationship("Doctor", foreign_keys=[prescribing_doctor_id], lazy="selectin")


class DoseChange(Base):
    __tablename__ = "dose_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prescription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("prescriptions.id"))
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"))
    requested_by_doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"))
    previous_dosage: Mapped[str] = mapped_column(String(100))
    new_dosage: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending_approval")
    approval_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_first_change: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    prescription = relationship("Prescription", lazy="selectin")
    patient = relationship("Patient", lazy="selectin")
    requested_by = relationship("Doctor", foreign_keys=[requested_by_doctor_id], lazy="selectin")
