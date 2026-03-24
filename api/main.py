from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.config import get_settings
from api.routes import request, rules, approvers, audit

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ApprovalKit API starting up")
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
