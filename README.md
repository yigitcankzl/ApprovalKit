# ApprovalKit

**Human Approval Middleware for AI Agents**

Auth0 Token Vault + CIBA + FGA | Authorized to Act Hackathon 2026

---

## What is ApprovalKit?

ApprovalKit is a plug-and-play human approval middleware platform for AI agents. Any agent that can make an HTTP request can integrate with it. LLM-agnostic, framework-agnostic, language-agnostic.

When an AI agent needs to take a high-stakes action (charging a credit card, deploying to production, publishing a package), a human must approve it first. ApprovalKit handles the entire approval workflow using three Auth0 capabilities:

- **Token Vault** — Secure credential storage. Tokens never reach the agent.
- **CIBA** — Human-in-the-loop push notification approval via Auth0 Guardian.
- **FGA** — Fine-grained authorization for the platform itself.

```
AI Agent → POST /api/v1/request → FastAPI → Rule Engine → Celery Worker
                                                              ↓
                                                   Auth0 CIBA (Guardian push)
                                                              ↓
                                                     Human approves/rejects
                                                              ↓
                                                   Token Vault → Target Service
```

The token **never reaches the agent**. After approval, the platform executes the action directly via Token Vault.

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Auth0 tenant with Token Vault, CIBA, and FGA enabled

### Setup

```bash
# Clone & configure
git clone <repo-url> && cd ApprovalKit
cp .env.example .env
cp frontend/.env.local.example frontend/.env.local
# Fill in Auth0 credentials in both files

# Start
docker compose up -d
docker compose exec api alembic upgrade head

# Generate API key + HMAC secret
docker compose exec api python scripts/setup.py

# Access
# Welcome:  http://localhost:3000
# API docs: http://localhost:8000/docs
```

---

## Python SDK

Install the SDK from the `sdk/` folder:

```bash
pip install ./sdk
```

Add one decorator to any function — everything else stays the same:

```python
from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url="http://localhost:8000",
    api_key="...",
    hmac_secret="...",
)

@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    stripe.charge(amount=amount, customer=customer)
    # this line only runs after a human approves

try:
    charge_customer(349, "alice@example.com")
except ApprovalDenied as e:
    print(f"Blocked: {e.status}")  # rejected | timeout | blocked
```

Or use the inline gate without a decorator:

```python
kit.gate("stripe-prod", "charge", {"amount": 349, "customer": "alice@example.com"})
# reaching here = approved
stripe.charge(...)
```

See `examples/shopping_bot.py` for a full working demo.

---

## Raw HTTP Integration

Works with any language or framework:

```python
import hmac, hashlib, time, json, requests, uuid

payload = {
    "connection": "stripe-prod",
    "action": "charge",
    "params": {"amount": 340, "customer": "john@example.com"},
    "user_id": "auth0|abc123",
    "idempotency_key": str(uuid.uuid4()),
}
body = json.dumps(payload, separators=(',', ':'))
ts   = str(int(time.time()))
sig  = hmac.new(HMAC_SECRET.encode(), f'{ts}.{body}'.encode(), hashlib.sha256).hexdigest()

r = requests.post(
    "http://localhost:8000/api/v1/request",
    json=payload,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "X-Signature": f"hmac-sha256={ts}.{sig}",
    },
)
# 202 → poll /api/v1/status/{job_id}
# 200 → pre-approved, proceed immediately
# 403 → blocked by rule
```

---

## Features

### Approval Models
| Model | Description |
|-------|-------------|
| `any_one` | First approval from any listed approver |
| `specific` | Only the designated person can approve |
| `all_of_n` | Every approver must approve |
| `k_of_n` | k out of n approvers within quorum window |
| `sequential` | Ordered chain (A → B → C) |

### Security
- HMAC-SHA256 request signing with 5-minute replay prevention
- Credential key isolation (`HMAC_SECRET` ≠ `CREDENTIALS_KEY`)
- Pydantic v2 validation with injection-safe action patterns
- Scope creep detection (new action type flagging + audit alert)
- FGA-enforced least privilege on all platform data
- Fail-closed FGA — partial config denies access instead of allowing

### Advanced
- Escalation chains with configurable timeouts
- Temporal delegation (forward approvals to backup approver)
- Pre-approval (blanket approval with conditions and expiry)
- Partial approval (approver modifies params before approving)
- Blackout windows (hard block during specific hours)
- Cooldown limits (max triggers per time window)
- CIBA quota tracking (Auth0 500/hour limit with warnings)
- Idempotency keys (prevents duplicate CIBA notifications)
- Simulation mode (test rules without real notifications)
- Sentry error tracking (optional, via `SENTRY_DSN`)

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/request` | Submit approval request |
| GET | `/api/v1/status/:id` | Poll job status |
| PATCH | `/api/v1/jobs/:id/params` | Approver modifies params (partial approval) |
| POST | `/api/v1/rules` | Create rule |
| GET | `/api/v1/rules` | List rules |
| GET | `/api/v1/rules/:id` | Get rule |
| PUT | `/api/v1/rules/:id` | Update rule |
| DELETE | `/api/v1/rules/:id` | Delete rule |
| POST | `/api/v1/rules/simulate` | Test rule without CIBA |
| POST | `/api/v1/approvers` | Create approver |
| GET | `/api/v1/approvers` | List approvers |
| PUT | `/api/v1/approvers/:id` | Update approver |
| DELETE | `/api/v1/approvers/:id` | Delete approver |
| PUT | `/api/v1/approvers/:id/delegate` | Set delegation |
| DELETE | `/api/v1/approvers/:id/delegate` | Remove delegation |
| GET | `/api/v1/audit` | Audit log (FGA-filtered) |
| GET | `/api/v1/dashboard` | Aggregated stats |
| GET | `/api/v1/security-status` | Live security status |
| GET | `/api/v1/ciba-quota` | CIBA usage (500/hour limit) |
| POST | `/api/v1/connections` | Create service connection |
| GET | `/api/v1/connections` | List connections |

---

## FGA Access Control

```
workspace_admin  → Full access to rules, approvers, audit, dashboard
approver         → Own approval history only
agent_owner      → Own agent's data only
viewer           → Summary dashboard only
```

---

## Auth0 Gap Analysis

ApprovalKit addresses 6 gaps in Auth0's current offering:

1. **n-of-m Approval Threshold** — CIBA is single-approver only
2. **Escalation Chains** — No built-in timeout routing
3. **Action-Scoped Tokens** — Token Vault has no per-action scoping
4. **Temporal Delegation** — No delegated approval authority
5. **Approval History Persistence** — CIBA is stateless, no persistent grants
6. **FGA for Approval Workflows** — FGA documented only for RAG, not approvals

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 + Tailwind + React Flow |
| HTTP API | FastAPI + Pydantic v2 |
| Worker | Celery + Redis |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Auth | Auth0 (Token Vault, CIBA, FGA) |
| Error Tracking | Sentry (optional) |

---

## Project Structure

```
ApprovalKit/
├── api/                    # FastAPI backend
│   ├── main.py             # App entrypoint + Sentry init
│   ├── config.py           # Settings (env vars)
│   ├── database.py         # SQLAlchemy async setup
│   ├── routes/             # request, rules, approvers, audit, connections
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic request/response schemas
│   ├── services/           # rule_engine, ciba, fga, token_vault
│   ├── worker/             # Celery tasks + state machine
│   ├── middleware/         # HMAC auth, rate limiting, FGA guards
│   └── migrations/         # Alembic migrations
├── frontend/               # Next.js 14
│   └── src/
│       ├── app/            # Pages: /, dashboard, rules, approvers,
│       │                   #        audit, gallery, simulate, docs,
│       │                   #        onboarding, connections
│       ├── components/     # UI components, sidebar, rule-builder, rule-graph
│       ├── lib/            # API client
│       └── types/          # TypeScript types
├── sdk/                    # pip-installable Python SDK
│   ├── pyproject.toml
│   └── approvalkit/        # ApprovalKit class + ApprovalDenied exception
├── examples/               # Integration demos
│   └── shopping_bot.py     # Full working demo with/without approval
├── scripts/                # Setup helpers
│   ├── setup.py            # Generate API key, HMAC secret, credentials key
│   ├── setup_auth0.py      # Auth0 tenant setup
│   └── setup_fga.py        # FGA store + model setup
├── fga/                    # Auth0 FGA model and tuples
├── tests/                  # Unit tests
├── docker-compose.yml
└── Dockerfile.api
```
