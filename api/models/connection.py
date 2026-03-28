import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class ServiceConnection(Base):
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    service: Mapped[str] = mapped_column(String(100), nullable=False)
    token_vault_connection_id: Mapped[str] = mapped_column(String(200), nullable=False)
    actions: Mapped[dict] = mapped_column(JSONB, default=list)
    # Short slug used in approval requests (e.g. "stripe-prod")
    slug: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    # Auth0 Token Vault — OAuth connected account
    connected_auth0_user_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    connected_user_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    auth0_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M2M Credential Vault — for APIs using client_credentials grant (Amadeus, Twilio, AWS, etc.)
    # These are encrypted at rest via Fernet (same as auth0_refresh_token).
    # Token Vault handles user-delegated OAuth; Credential Vault handles M2M API keys.
    m2m_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)       # encrypted client_secret / API key
    m2m_client_id: Mapped[str | None] = mapped_column(String(200), nullable=True)  # client_id for token endpoint
    m2m_token_url: Mapped[str | None] = mapped_column(Text, nullable=True)     # token endpoint URL

    # Generic webhook execution config (for custom/unsupported services)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_method: Mapped[str | None] = mapped_column(String(10), nullable=True)  # GET/POST/PUT/PATCH/DELETE
    webhook_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)     # {"Authorization": "Bearer {{token}}"}
    webhook_body_template: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {"amount": "{{amount}}"}
    config_meta: Mapped[dict | None] = mapped_column("config_meta", JSONB, nullable=True)  # {"owner": "acme", "repo": "api"}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="connections")
