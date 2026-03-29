import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    npi: Mapped[str] = mapped_column(String(20), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(20))
    specialty: Mapped[str] = mapped_column(String(100))
    department: Mapped[str] = mapped_column(String(100))
    license_number: Mapped[str] = mapped_column(String(50))
    is_cmo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    on_vacation: Mapped[bool] = mapped_column(Boolean, default=False)
    delegate_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True
    )
    delegate_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approver_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    delegate = relationship("Doctor", remote_side="Doctor.id", lazy="selectin")
