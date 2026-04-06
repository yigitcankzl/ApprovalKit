"""
Shared async Redis connection pool.

`redis.asyncio.from_url` lazily manages a pool under the hood, but a
process should only create ONE client per URL. Every module that needed
Redis used to do `aioredis.from_url(...)` on each call — that churned
connections and hit max-clients in production.

This module keeps a single `Redis` instance per URL and exposes a
`get_redis()` helper. Call `aclose_all()` on shutdown.
"""
from __future__ import annotations

from typing import Dict

import redis.asyncio as aioredis

from api.config import get_settings

_settings = get_settings()
_clients: Dict[str, aioredis.Redis] = {}


def get_redis(url: str | None = None) -> aioredis.Redis:
    """Return a shared Redis client for the given URL (defaults to REDIS_URL).

    The client owns an internal connection pool — safe to share across
    tasks. Do NOT close it per request; call ``aclose_all()`` only on
    application shutdown.
    """
    key = url or _settings.REDIS_URL
    client = _clients.get(key)
    if client is None:
        client = aioredis.from_url(key, decode_responses=True, max_connections=50)
        _clients[key] = client
    return client


async def aclose_all() -> None:
    """Close every pooled client. Call from FastAPI lifespan shutdown."""
    for client in list(_clients.values()):
        try:
            await client.aclose()
        except Exception:
            pass
    _clients.clear()
