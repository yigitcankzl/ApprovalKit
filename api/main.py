from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from api.config import get_settings
import api.models  # noqa: F401 — registers all ORM mappers before any query runs
from api.routes import request, rules, approvers, audit, connections, workspace, consent, demo

settings = get_settings()

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.2,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,
    )
    logger.info("Sentry error tracking enabled")
else:
    logger.warning("SENTRY_DSN not configured — error tracking disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ApprovalKit API starting up")
    from api.services.fga import fga_client
    fga_client._warn_if_misconfigured()
    yield
    logger.info("ApprovalKit API shutting down")
    from api.middleware.rate_limit import rate_limiter
    await rate_limiter.close()


app = FastAPI(
    title="ApprovalKit",
    description="Human Approval Middleware for AI Agents — Auth0 Token Vault + CIBA + FGA",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(request.router)
app.include_router(rules.router)
app.include_router(approvers.router)
app.include_router(audit.router)
app.include_router(connections.router)
app.include_router(workspace.router)
app.include_router(consent.router)
app.include_router(demo.router)


@app.get("/")
async def root():
    return {
        "name": "ApprovalKit",
        "version": "1.0.0",
        "description": "Human Approval Middleware for AI Agents",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
