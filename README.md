# ApprovalKit

**Human Approval Middleware for AI Agents**

Auth0 Token Vault + CIBA + FGA | Authorized to Act Hackathon 2026

## What is ApprovalKit?

ApprovalKit is a plug-and-play human approval middleware platform for AI agents. Any agent that can make an HTTP request can integrate with it. LLM-agnostic, framework-agnostic, language-agnostic.

When an AI agent needs to take a high-stakes action (charging a credit card, deploying to production, publishing a package), a human must approve it first. ApprovalKit handles the entire approval workflow using three Auth0 capabilities:

- **Token Vault** — Secure credential storage. Tokens never reach the agent.
- **CIBA** — Human-in-the-loop push notification approval.
- **FGA** — Fine-grained authorization for the platform itself.

## Architecture

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

## Features

### Approval Models
- **any-one** — First approval from any listed approver
- **specific** — Only designated person can approve
- **all-of-n** — Every approver must approve
- **k-of-n** — k out of n approvers within quorum window
- **sequential** — Ordered chain (A → B → C)

### Security
- HMAC-SHA256 request signing with 5-minute replay prevention
- Pydantic v2 validation with injection-safe action patterns
- Scope creep detection (new action type flagging)
- FGA-enforced least privilege on all platform data
- One-click Token Vault connection revocation

### Advanced
- Escalation chains with configurable timeouts
- Temporal delegation (forward approvals to backup)
- Pre-approval (blanket approval with conditions and expiry)
- Partial approval (approver modifies params)
- Blackout windows (hard block during hours)
- Cooldown limits (max triggers per hour)
- CIBA quota tracking (Auth0 500/hour limit)
- Idempotency keys (no duplicate CIBA)
- Simulation mode (test rules without real notifications)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 + Tailwind + React Flow |
| HTTP API | FastAPI + Pydantic v2 |
| Worker | Celery + Redis |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Auth | Auth0 (Token Vault, CIBA, FGA) |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Auth0 tenant with Token Vault, CIBA, and FGA enabled

### Setup

```bash
# Clone
git clone <repo-url> && cd approvalkit

# Configure
cp .env.example .env
cp frontend/.env.local.example frontend/.env.local
# Edit both files with your Auth0 credentials

# Run
docker-compose up -d

# Migrate database
docker-compose exec api alembic upgrade head

# Access
# API:      http://localhost:8000/docs
# Frontend: http://localhost:3000
```

### Agent Integration

```python
import hmac, hashlib, time, json, requests

timestamp = str(int(time.time()))
payload = {
    "connection": "stripe-prod",
    "action": "charge",
    "params": {"amount": 340, "customer": "john@example.com"},
    "user_id": "auth0|abc123",
    "idempotency_key": "req_7f3a9b2c-1234-5678-9abc-def012345678"
}
body = json.dumps(payload, separators=(',', ':'))
sig = hmac.new(SECRET.encode(), f'{timestamp}.{body}'.encode(), hashlib.sha256).hexdigest()

response = requests.post(
    "http://localhost:8000/api/v1/request",
    json=payload,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "X-Signature": f"hmac-sha256={timestamp}.{sig}"
    }
)

# 202 Accepted → poll /api/v1/status/{job_id}
# 200 OK       → pre-approved, proceed
# 403 Forbidden → blocked
```

## FGA Access Control

```
workspace_admin  → Full access to rules, approvers, audit, dashboard
approver         → Own approval history only
agent_owner      → Own agent's data only
viewer           → Summary dashboard only
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/request` | Submit approval request |
| GET | `/api/v1/status/:id` | Poll job status |
| POST | `/api/v1/rules` | Create rule |
| GET | `/api/v1/rules` | List rules |
| PUT | `/api/v1/rules/:id` | Update rule |
| POST | `/api/v1/rules/simulate` | Test without CIBA |
| GET | `/api/v1/audit` | Audit log (FGA-filtered) |
| GET | `/api/v1/dashboard` | Stats (FGA-filtered) |
| POST | `/api/v1/approvers` | Create approver |
| PUT | `/api/v1/approvers/:id/delegate` | Set delegation |
| POST | `/api/v1/connections/:id/revoke` | Revoke connection |
| GET | `/api/v1/ciba-quota` | CIBA usage stats |

## Auth0 Gap Analysis

ApprovalKit addresses 6 gaps in Auth0's current offering:

1. **n-of-m Approval Threshold** — CIBA is single-approver only
2. **Escalation Chains** — No built-in timeout routing
3. **Action-Scoped Tokens** — Token Vault has no per-action scoping
4. **Temporal Delegation** — No delegated approval authority
5. **Approval History Persistence** — CIBA is stateless, no persistent grants
6. **FGA for Approval Workflows** — FGA documented only for RAG, not approvals

## Project Structure

```
approvalkit/
├── api/                    # FastAPI backend
│   ├── main.py            # App entrypoint
│   ├── config.py          # Settings
│   ├── database.py        # SQLAlchemy async setup
│   ├── routes/            # API endpoints
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Rule engine, CIBA, FGA, Token Vault
│   ├── worker/            # Celery tasks + state machine
│   ├── middleware/        # HMAC auth + rate limiting
│   └── migrations/        # Alembic migrations
├── frontend/              # Next.js 14
│   └── src/
│       ├── app/           # Pages (dashboard, rules, audit, gallery, simulate)
│       ├── components/    # UI, rule-builder, rule-graph (React Flow)
│       ├── lib/           # API client, utils
│       └── types/         # TypeScript types
├── fga/                   # Auth0 FGA model and tuples
├── docker-compose.yml
└── Dockerfile.api
```
