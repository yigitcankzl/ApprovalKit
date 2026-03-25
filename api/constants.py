"""
Shared constants — Redis key patterns, limits, etc.
"""

# Redis key patterns
REDIS_KEY_RATE_LIMIT = "rl:{key}"          # per-API-key rate limit sorted set
REDIS_KEY_CIBA_QUOTA = "ciba:quota"        # CIBA push quota sorted set (hourly)
REDIS_KEY_COOLDOWN = "cooldown:{rule_id}"  # per-rule cooldown counter
REDIS_KEY_IDEMPOTENCY = "idem:{key}"       # idempotency dedup key
REDIS_KEY_SSE_CHANNEL = "sse:activity"     # SSE pub/sub channel for live feed

# Limits
MAX_BODY_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB
COOLDOWN_WINDOW_SECONDS = 3600          # 1 hour
CIBA_QUOTA_WINDOW_SECONDS = 3600        # 1 hour
