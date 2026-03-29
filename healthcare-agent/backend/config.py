"""
Healthcare AI Agent — Configuration
"""
import os


class Settings:
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://healthcare:healthcare@localhost:5433/healthcare_agent",
    )
    DATABASE_URL_SYNC: str = os.getenv(
        "DATABASE_URL_SYNC",
        "postgresql://healthcare:healthcare@localhost:5433/healthcare_agent",
    )

    # ApprovalKit
    APPROVALKIT_URL: str = os.getenv("APPROVALKIT_URL", "http://localhost:8000")
    APPROVALKIT_API_KEY: str = os.getenv("APPROVALKIT_API_KEY", "")
    APPROVALKIT_HMAC_SECRET: str = os.getenv("APPROVALKIT_HMAC_SECRET", "")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "3002"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # CORS
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3003")

    # Hospital
    HOSPITAL_NAME: str = os.getenv("HOSPITAL_NAME", "MedCore General Hospital")
    HOSPITAL_EMAIL: str = os.getenv("HOSPITAL_EMAIL", "admin@medcore-hospital.com")


settings = Settings()
