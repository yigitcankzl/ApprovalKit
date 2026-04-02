"""
Lightweight startup migrations — ADD COLUMN IF NOT EXISTS.
Each migration is idempotent; safe to run on every startup.
"""
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


MIGRATIONS: list[tuple[str, str]] = [
    # Feature 7: Risk-based scoring stored on each job
    (
        "approval_jobs.risk_score",
        "ALTER TABLE approval_jobs ADD COLUMN IF NOT EXISTS risk_score INTEGER DEFAULT 0",
    ),
    (
        "approval_jobs.risk_level",
        "ALTER TABLE approval_jobs ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) DEFAULT 'low'",
    ),
    # Feature 7: Auto-approve threshold on rules (0 = disabled)
    (
        "rules.risk_auto_approve_threshold",
        "ALTER TABLE rules ADD COLUMN IF NOT EXISTS risk_auto_approve_threshold INTEGER DEFAULT NULL",
    ),
    # Feature 4: Denial feedback — store rejection reason on the job
    (
        "approval_jobs.rejection_reason",
        "ALTER TABLE approval_jobs ADD COLUMN IF NOT EXISTS rejection_reason TEXT DEFAULT NULL",
    ),
    # Feature 8: Agent Trust Score
    (
        "registered_agents.trust_score",
        "ALTER TABLE registered_agents ADD COLUMN IF NOT EXISTS trust_score INTEGER DEFAULT 100",
    ),
    (
        "registered_agents.trust_history",
        "ALTER TABLE registered_agents ADD COLUMN IF NOT EXISTS trust_history JSONB DEFAULT '[]'",
    ),
]


async def run_migrations(db: AsyncSession) -> None:
    """Run all pending schema migrations. Called once at startup."""
    for name, sql in MIGRATIONS:
        try:
            await db.execute(text(sql))
            logger.debug(f"Migration OK: {name}")
        except Exception as exc:
            logger.warning(f"Migration skipped ({name}): {exc}")
    await db.commit()
    logger.info(f"Migrations complete ({len(MIGRATIONS)} statements)")
