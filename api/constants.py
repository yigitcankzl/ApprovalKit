"""
Shared constants — Redis key patterns, limits, etc.
"""

# Redis key patterns
REDIS_KEY_RATE_LIMIT = "rl:{key}"          # per-API-key rate limit sorted set
REDIS_KEY_CIBA_QUOTA = "ciba:quota"        # CIBA push quota sorted set (hourly)
REDIS_KEY_COOLDOWN = "cooldown:{rule_id}"  # per-rule cooldown counter
REDIS_KEY_IDEMPOTENCY = "idem:{key}"       # idempotency dedup key
REDIS_KEY_SSE_CHANNEL = "sse:activity"     # SSE pub/sub channel for live feed

# Forbidden param keys (injection prevention)
FORBIDDEN_PARAM_KEYS = {"__proto__", "constructor", "$where", "__prototype__"}

# Execution mode — who runs the approved action.
#   "client" — ApprovalKit only does policy/approval/audit; the SDK (the
#              caller) runs the action after approval. This is the default
#              for new SDKs and the local-first quickstart.
#   "server" — ApprovalKit runs the action server-side via an ActionExecutor
#              (e.g. Auth0 Token Vault). Legacy behavior; kept for REST
#              backward-compatibility when the field is omitted.
EXECUTION_MODE_CLIENT = "client"
EXECUTION_MODE_SERVER = "server"
EXECUTION_MODES = {EXECUTION_MODE_CLIENT, EXECUTION_MODE_SERVER}
# REST requests that omit execution_mode default to "server" so existing
# integrations keep their server-side execution behavior.
DEFAULT_EXECUTION_MODE = EXECUTION_MODE_SERVER

# Default notification channels
DEFAULT_NOTIFY_CHANNELS = ["guardian_push"]
DEFAULT_URGENT_CHANNELS = ["guardian_push"]

# Limits
MAX_BODY_SIZE_BYTES = 1 * 1024 * 1024       # 1 MB
COOLDOWN_WINDOW_SECONDS = 3600               # 1 hour
CIBA_QUOTA_WINDOW_SECONDS = 3600             # 1 hour
SCOPE_CREEP_LOOKBACK = 100                   # historical jobs to check
ANOMALY_THRESHOLD_MULTIPLIER = 3             # current > avg * N = anomaly
AUTH_SESSION_TTL_SECONDS = 600               # 10 min Redis TTL for OAuth sessions
IDEMPOTENCY_TTL_SECONDS = 86400              # 24 hour TTL for idempotency keys
DECISION_RATE_LIMIT_PER_JOB = 5              # max decisions per job per minute
DECISION_RATE_WINDOW_SECONDS = 60

# Budget tracking Redis key patterns
REDIS_KEY_BUDGET_DAILY = "budget:daily:{agent_id}"
REDIS_KEY_BUDGET_WEEKLY = "budget:weekly:{agent_id}"
REDIS_KEY_BUDGET_MONTHLY = "budget:monthly:{agent_id}"
BUDGET_DAILY_TTL = 86400          # 24 hours
BUDGET_WEEKLY_TTL = 604800        # 7 days
BUDGET_MONTHLY_TTL = 2678400      # 31 days

# Default budget limits (per agent) — override via BUDGET_DAILY_LIMIT etc. env vars
DEFAULT_BUDGET_LIMITS = {
    "daily": 50_000,
    "weekly": 200_000,
    "monthly": 500_000,
}

# Agent rate limiting (per-agent hourly request counter)
REDIS_KEY_AGENT_RATE = "agent_rate:{agent_id}:{connection}"
AGENT_RATE_WINDOW_SECONDS = 3600  # 1 hour sliding window

# Approval expiry (approved but not executed within window → void)
DEFAULT_APPROVAL_EXPIRY_SECONDS = 1800  # 30 minutes

# Re-authorization: consecutive approval counter per agent+connection+action
REDIS_KEY_REAUTH_COUNTER = "reauth:{agent_id}:{connection}:{action}"
REAUTH_COUNTER_TTL = 86400  # 24 hours — resets daily

# Webhook
WEBHOOK_TIMEOUT_SECONDS = 10
WEBHOOK_MAX_RETRIES = 3
