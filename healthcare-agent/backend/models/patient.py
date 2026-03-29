import uuid
from datetime import datetime, date
from sqlalchemy import String, Date, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mrn: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(10))
    ssn_masked: Mapped[str] = mapped_column(String(15))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(320))
    address: Mapped[dict] = mapped_column(JSONB, default=dict)
    emergency_contact: Mapped[dict] = mapped_column(JSONB, default=dict)
    blood_type: Mapped[str] = mapped_column(String(5))
    allergies: Mapped[list] = mapped_column(JSONB, default=list)
    conditions: Mapped[list] = mapped_column(JSONB, default=list)
    medications_current: Mapped[list] = mapped_column(JSONB, default=list)
    primary_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True
    )
    insurance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_providers.id"), nullable=True
    )
    insurance_policy_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    primary_doctor = relationship("Doctor", foreign_keys=[primary_doctor_id], lazy="selectin")
    insurance = relationship("InsuranceProvider", foreign_keys=[insurance_id], lazy="selectin")
    prescriptions = relationship("Prescription", back_populates="patient", lazy="selectin")
    appointments = relationship("Appointment", back_populates="patient", lazy="selectin")
    billing_records = relationship("BillingRecord", back_populates="patient", lazy="selectin")
