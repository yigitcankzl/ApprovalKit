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
import sys

# Structured logging setup
logger.remove()
if get_settings().ENVIRONMENT == "production":
    logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", level="INFO")
else:
    logger.add(sys.stderr, format="{time:HH:mm:ss} | {level:<7} | {message}", level="DEBUG", colorize=True)
from api.routes import request, rules, approvers, audit, connections, workspace, consent, demo, agents, agent_chat, auth0_webhook, email_approval, auth0_logs

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

from api.constants import MAX_BODY_SIZE_BYTES as MAX_BODY_SIZE


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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Signature", "X-Fga-User", "X-User-Sub", "X-User-Token", "X-Refresh-Token"],
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
app.include_router(agent_chat.router)
app.include_router(agents.router)
app.include_router(auth0_webhook.router)
app.include_router(email_approval.router)
app.include_router(auth0_logs.router)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Return 400 for invalid UUIDs and other value errors instead of 500."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


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


@app.get("/health/deep")
async def health_deep():
    """Deep health check — verifies DB, Redis, and Ollama connectivity."""
    checks = {}

    # DB check
    try:
        from api.database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:50]}"

    # Redis check
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:50]}"

    # Ollama check
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get("http://ollama:11434/api/tags")
            checks["ollama"] = "ok" if resp.status_code == 200 else f"status: {resp.status_code}"
    except Exception as e:
        checks["ollama"] = f"error: {str(e)[:50]}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "healthy" if all_ok else "degraded", "checks": checks}


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    """Add trace_id to every request for distributed tracing."""
    import uuid as _uuid
    trace_id = request.headers.get("X-Trace-Id", str(_uuid.uuid4())[:8])
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response
