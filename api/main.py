from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from loguru import logger
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from api.config import get_settings
import api.models  # noqa: F401 — registers all ORM mappers before any query runs
from api.routes import request, rules, approvers, audit, connections, workspace, consent, demo, agents

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

MAX_BODY_SIZE = 1 * 1024 * 1024  # 1 MB


class LimitRequestBodyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large. Maximum size is {MAX_BODY_SIZE} bytes."},
            )
        return await call_next(request)


_allowed_origins = [
    origin.strip()
    for origin in (settings.FRONTEND_URL or "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LimitRequestBodyMiddleware)

app.include_router(request.router)
app.include_router(rules.router)
app.include_router(approvers.router)
app.include_router(audit.router)
app.include_router(connections.router)
app.include_router(workspace.router)
app.include_router(consent.router)
app.include_router(demo.router)
app.include_router(agents.router)


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
