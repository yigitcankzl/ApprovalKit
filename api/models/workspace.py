import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    auth0_tenant: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    hmac_secret: Mapped[str] = mapped_column(String(128), nullable=False)
    # Per-workspace Auth0 credentials (overrides .env)
    auth0_domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    auth0_m2m_client_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    auth0_m2m_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth0_web_client_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    auth0_web_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth0_audience: Mapped[str | None] = mapped_column(String(300), nullable=True)
    auth0_mgmt_api_audience: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Per-workspace FGA credentials
    fga_api_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    fga_store_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fga_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fga_client_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fga_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    credentials_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_auth0_sub: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    rules = relationship("Rule", back_populates="workspace", lazy="selectin")
    approvers = relationship("Approver", back_populates="workspace", lazy="selectin")
    connections = relationship("ServiceConnection", back_populates="workspace", lazy="selectin")
