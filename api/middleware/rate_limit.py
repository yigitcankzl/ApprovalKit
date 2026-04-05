import time
from fastapi import HTTPException, Request

import redis.asyncio as aioredis

from api.config import get_settings
from api.constants import REDIS_KEY_RATE_LIMIT, REDIS_KEY_CIBA_QUOTA, CIBA_QUOTA_WINDOW_SECONDS

settings = get_settings()


class RateLimiter:
    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def check_rate_limit(self, key: str, max_requests: int = 100, window_seconds: int = 3600) -> bool:
        r = await self.get_redis()
        pipe = r.pipeline()
        now = time.time()
        window_start = now - window_seconds

        redis_key = REDIS_KEY_RATE_LIMIT.format(key=key)
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zadd(redis_key, {str(now): now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_seconds)
        results = await pipe.execute()

        current_count = results[2]
        return current_count < max_requests

    async def check_ciba_quota(self) -> dict:
        r = await self.get_redis()
        now = time.time()
        window_start = now - 3600
        count = await r.zcount(REDIS_KEY_CIBA_QUOTA, window_start, now)
        return {
            "current": count,
            "limit": settings.CIBA_QUOTA_LIMIT,
            "percentage": round(count / settings.CIBA_QUOTA_LIMIT * 100, 1),
            "warning": count >= settings.CIBA_QUOTA_LIMIT * settings.CIBA_QUOTA_WARN_PERCENT / 100,
        }

    async def record_ciba_request(self):
        r = await self.get_redis()
        now = time.time()
        await r.zadd(REDIS_KEY_CIBA_QUOTA, {str(now): now})
        await r.expire(REDIS_KEY_CIBA_QUOTA, CIBA_QUOTA_WINDOW_SECONDS)

    async def close(self):
        if self._redis:
            await self._redis.close()


rate_limiter = RateLimiter()


def _client_ip(request: Request) -> str:
    """Extract the client IP, honouring X-Forwarded-For when behind a proxy."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        # Take the first IP in the chain (closest to origin).
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def check_api_rate_limit(request: Request):
    api_key = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if api_key:
        allowed = await rate_limiter.check_rate_limit(
            key=f"apikey:{api_key}",
            max_requests=settings.API_RATE_LIMIT,
        )
    else:
        # Unauthenticated: rate-limit by client IP so public endpoints
        # (email approval, /health/deep, OAuth callbacks) cannot be
        # brute-forced or DoS'd anonymously.
        ip = _client_ip(request)
        allowed = await rate_limiter.check_rate_limit(
            key=f"ip:{ip}",
            max_requests=max(20, settings.API_RATE_LIMIT // 4),
            window_seconds=3600,
        )
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
