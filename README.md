# ApprovalKit

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)](sdk/)
[![TypeScript](https://img.shields.io/badge/typescript-5.x-blue?logo=typescript)](sdk-ts/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](docker-compose.yml)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple)](sdk/approvalkit/mcp_server.py)
[![Auth0 Token Vault](https://img.shields.io/badge/Auth0-Token%20Vault-EB5424?logo=auth0)](https://auth0.com/ai/docs/intro/token-vault)
[![status](https://img.shields.io/badge/status-beta-yellow)](#project-status)

**Human approval gateway for AI agents.** Wrap any high-stakes function in a human approval gate — policy, approval, and audit are handled for you; your code runs only after a human says yes.

> One decorator. Any agent. Local-first. Auth0 optional.

```
pip install ./sdk
```

```python
# Default (client execution): your function runs after a human approves.
@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount, email):
    return stripe.Charge.create(amount=amount, customer=email)

receipt = charge_customer(amount=150, email="alice@example.com")
```

No Auth0 account, no credentials, no cloud dependency required to start — bring up the local stack and you have a working approval flow in minutes. Auth0 (CIBA push + Token Vault server-side execution) is an optional, production-grade **provider** you can switch on later.

Works with **LangChain**, **CrewAI**, **OpenAI Function Calling**, **Claude MCP**, or any Python/TypeScript agent.

---

## The Problem

AI agents are increasingly autonomous — they can book flights, deploy code, charge credit cards, send emails. But **what happens when they make a mistake?** A wrong Stripe charge, an accidental production deploy, or an unauthorized email can't be undone.

Today, most agents hold raw API keys in memory. If the agent is compromised, or if it hallucinates, there's no safety net. No human reviews the action. No audit trail exists.

## The Solution

ApprovalKit is a **plug-and-play middleware** that sits between AI agents and the services they control. When an agent wants to take a high-stakes action, ApprovalKit:

1. **Evaluates the request** against configurable rules
2. **Notifies the right human** through the configured approval channel (local dashboard/HTTP by default, or Auth0 CIBA + Guardian push in production)
3. **Waits for approval** and records a full audit trail
4. **Hands control back** — in the default **client execution mode**, your code runs the action after approval; in **server execution mode**, ApprovalKit runs it for you via a provider (e.g. Auth0 Token Vault, so the agent never sees credentials)

```
AI Agent                          Human
   |                                |
   |  POST /api/v1/request          |
   |──────────────> ApprovalKit     |
   |                   |            |
   |           Rule Engine          |
   |           Step-up check        |
   |                   |            |
   |           Auth0 CIBA ─────────>| Guardian push
   |                                | "Charge $349 for alice?"
   |                                |
   |                   |<───────────| Approve
   |                   |            |
   |           Token Vault          |
   |           (RFC 8693)           |
   |           Stripe charge ✓      |
   |<──────────────────|            |
   |  {status: approved}            |
```

The agent adds **one decorator** to any function:

```python
from approvalkit import ApprovalKit

# Client execution mode is the default — your function runs after approval.
kit = ApprovalKit(base_url="...", api_key="...", hmac_secret="...")

@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    return stripe.Charge.create(amount=amount, customer=customer)

# Prefer ApprovalKit to run the action for you (Auth0 Token Vault, no creds in
# the agent)? Opt into server execution mode:
kit = ApprovalKit(..., execution_mode="server")  # function body is not run
```

### Execution modes

| | `client` (default) | `server` (legacy / Auth0) |
|---|---|---|
| Who runs the action | **Your code**, after approval | ApprovalKit, via an `ActionExecutor` provider |
| Credentials | Stay in your process | Held by the provider (agent never sees them) |
| Requires Auth0 | No | For Token Vault execution, yes |
| `gate()` returns | Approval result (you act on it) | Approval result (already executed) |
| Decorated fn body | Runs with approved params | Never runs |

> REST note: requests that omit `execution_mode` default to `server` for backward
> compatibility. The SDKs and MCP server send `client` by default.

---

## Quickstart (local-first, no Auth0)

```bash
# 1. Bring up the local stack (Postgres + Redis + API + worker, no Auth0/Ollama)
docker compose -f docker-compose.local.yml up

# 2. Install the SDK and gate a function — your code runs after approval
pip install ./sdk
```

Pending approvals are listed at `GET /local-approvals` and can be approved or
rejected over HTTP — no log scraping:

```bash
curl http://localhost:8000/local-approvals
curl -X POST http://localhost:8000/local-approvals/<handle>/approve
```

See [docs/quickstart.md](docs/quickstart.md) for the full walkthrough and
[docs/providers.md](docs/providers.md) for switching on the Auth0 provider.

---

## Auth0 Integration

ApprovalKit uses **three Auth0 capabilities**:

### Token Vault (RFC 8693 Token Exchange)

Credentials are stored in Auth0 Token Vault via the **Connected Accounts** flow. When an action is approved, ApprovalKit exchanges the user's refresh token for a fresh provider access token using the Token Exchange endpoint — the agent never sees the raw credential.

```
POST /oauth/token
grant_type=urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token
subject_token={auth0_refresh_token}
connection={stripe|github|slack|...}
```

All actions execute through **Auth0 Token Vault** — the agent never sees credentials. Token Vault supports 26+ OAuth providers:

| Category | Services |
|----------|----------|
| **Payments** | Stripe, PayPal, Shopify, Freshbooks |
| **Code & DevOps** | GitHub, Bitbucket, DigitalOcean |
| **Communication** | Slack, Discord, Microsoft Outlook |
| **Productivity** | Google (Gmail, Calendar, Drive, Sheets), Microsoft, Notion, Jira, Linear, HubSpot, Basecamp |
| **Storage** | Dropbox, Box, Google Drive, OneDrive |
| **Social** | X (Twitter), Twitch, Snapchat, Tumblr, Spotify |
| **Data & AI** | Amazon, Figma, Hugging Face, Fitbit |
| **Enterprise** | Salesforce, Microsoft Entra (Azure AD), Google Workspace |

ApprovalKit has **26 built-in service handlers** covering Token Vault providers — Stripe, GitHub, Slack, Google (Gmail/Calendar/Drive/Sheets), Microsoft (Outlook/OneDrive), Salesforce, Notion, Jira, Discord, Linear, HubSpot, Shopify, PayPal, Dropbox, Box, Bitbucket, Figma, Spotify, Twitch, Fitbit, Freshbooks, DigitalOcean, Basecamp, Hugging Face, Amadeus.

Existing MCP servers (GitHub, Slack, Stripe, etc.) give agents **direct API access with no oversight**. ApprovalKit sits in front — same actions, but with human approval, credential isolation via Token Vault, and full audit trail.

### CIBA (Client-Initiated Backchannel Authentication)

Human-in-the-loop approval via Auth0 Guardian push notifications. The approver sees a binding message on their phone (e.g., "Charge $349 for alice@example.com") and taps Approve or Deny.

### FGA (Fine-Grained Authorization)

Role-based access control for the platform itself: admins see everything, approvers see only their own history, viewers see aggregated stats.

---

## Key Features

### Step-up Authentication

Low-value actions auto-approve or need one person. High-value actions automatically escalate:

```
$49 charge   → auto-approve (no rule match)
$349 charge  → any_one (single manager approval)
$5000 charge → step-up → all_of_n (manager + CFO both approve)
```

Step-up conditions are configurable per rule. The Celery worker evaluates conditions at runtime and escalates the approval model before dispatching.

### 6 Approval Models

| Model | How it works |
|-------|-------------|
| `any_one` | First approval from any listed approver |
| `specific` | Only the designated person can approve |
| `all_of_n` | Every approver must approve |
| `k_of_n` | k out of n within a quorum time window |
| `sequential` | Ordered chain — each step waits for the previous |
| `fga_dynamic` | Auth0 FGA resolves approvers at runtime |

### AI Orchestrator & Sub-Agents

The live demo features a multi-agent orchestrator powered by local LLM (Qwen 2.5 7B). Describe any business situation and the orchestrator:

1. Plans a multi-agent workflow (selects agents, assigns per-step tools)
2. Runs **code-based pre-execution checks** (risk scoring, cost estimation) — instant, no LLM hallucination
3. Runs **LLM compliance + rollback analysis** for semantic regulatory checks
4. Executes the chain with verified action passing between agents
5. Validates each step with a **deterministic validator** (amount match, duplicates, scope creep)
6. Generates structured audit trail (hash-chained for tamper evidence) + executive summary

24+ preset scenarios across finance, security, HR, compliance, and **rogue agent testing** (demonstrates ApprovalKit blocking malicious actions).

### Consent & Permissions

A centralized page shows what agents can access, which services are connected, OAuth scopes granted, and allows instant revocation.

### Multi-tenant

Each organization stores its own Auth0 and FGA credentials in the database (encrypted at rest with Fernet). No `.env` editing — everything configured through the dashboard.

### Real-time Dashboard

SSE live feed via Redis pub/sub shows approval events as they happen. Pending approvals panel with live countdown timers, CIBA quota tracking, risk distribution visualization, and security status monitoring.

### Time-Boxed Approvals

Approved actions expire if not executed within a configurable window (`approval_expiry_seconds`). The dashboard shows live countdown timers on each pending job, with pulse animation for urgent items (<2 min remaining).

### Risk Score Visualization

Every request gets a 0-100 risk score based on amount, scope creep signals, approval model complexity, and step-up eligibility. The dashboard displays risk distribution (low/medium/high/critical) with per-connection breakdown.

### Per-Rule Budget Limits

Rules can define `budget_limits` (daily/weekly/monthly) to cap spending per approval flow. Combined with `allowed_days` (weekday restrictions) for scheduled approval windows.

### Permission Map

A dedicated view shows which agents can access which services, with OAuth scopes, approval models, and 7-day usage statistics per agent per connection. Trust scores are displayed per agent.

### Re-Authorization

After `reauth_every_n` consecutive approvals for the same agent+connection+action, a fresh human approval is forced — preventing rubber-stamping of repeated sensitive operations.

### Agent Activity Timeline

Each agent has a chronological activity timeline showing every request with risk scores, durations, approval rates, and rejection reasons.

---

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   AI Agent   │───>│  ApprovalKit │───>│  Auth0 CIBA  │───>│    Human     │
│  (any LLM)  │    │  FastAPI +   │    │  Guardian    │    │  (phone)     │
│              │    │  Celery      │    │  Push        │    │              │
└──────────────┘    └──────┬───────┘    └──────────────┘    └──────┬───────┘
                           │                                       │
                    Rule Engine                              Approve/Deny
                    Step-up eval                                   │
                           │            ┌──────────────┐           │
                           └───────────>│ Auth0 Token  │<──────────┘
                                        │ Vault (8693) │
                                        └──────┬───────┘
                                               │
                                        ┌──────┴───────┐
                                        │  Stripe /    │
                                        │  GitHub /    │
                                        │  Slack / ... │
                                        └──────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| API | Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| Worker | Celery 5.4, Redis 7 (circuit breaker, rate limiting, sessions) |
| Database | PostgreSQL 16, 10 migrations, Fernet encryption at rest |
| Frontend | Next.js 14, React 18, Tailwind CSS, TypeScript, dark mode |
| Auth | Auth0 Token Vault, CIBA, FGA, nextjs-auth0 v4, per-agent HMAC |
| SDK | Python + TypeScript, pip-installable, sync + async, jitter polling |
| Execution | 26 built-in handlers, all via Auth0 Token Vault |
| AI Agents | 10 specialized agents, code-based sub-agents, LLM compliance/summary |
| Infrastructure | Docker Compose (7 services), Ollama GPU support, non-root containers |

---

## Quick Start

Pick a flavour:

### Auth0 (production-grade)

```bash
git clone https://github.com/yigitcankzl/ApprovalKit.git
cd ApprovalKit
cp .env.example .env
# Edit .env with your Auth0 credentials (see SETUP.md)
chmod +x setup.sh
./setup.sh
```

Starts PostgreSQL, Redis, Vault, Ollama, API, Worker, and Frontend.
Open `http://localhost:3000`.

> **⏱️ Setup time:** ~5 min for services + 5-30 min for the one-time AI model download (4.7 GB). Use a free [Groq API key](https://console.groq.com) to skip the download.

### Local (no Auth0 required)

```bash
git clone https://github.com/yigitcankzl/ApprovalKit.git
cd ApprovalKit
cp .env.example .env
# Set APPROVAL_PROVIDER=local in .env
docker compose -f docker-compose.yml -f docker-compose.demo.yml up
```

The local backend swaps Auth0 CIBA for a Redis-backed HTTP approval
flow and Token Vault for a Fernet-encrypted local store. Best for
development, evaluations, and CI. See [`docs/providers.md`](docs/providers.md).

**Detailed docs live in [`docs/`](docs/) — start with [`docs/quickstart.md`](docs/quickstart.md). For the full Auth0 walkthrough see [`SETUP.md`](SETUP.md).**

---

## Security Model

1. **Token Vault** — Credentials never stored locally, never reach the agent
2. **Token Exchange (RFC 8693)** — Standard-compliant federated token retrieval
3. **Connected Accounts** — Proper Token Vault flow via My Account API
4. **Per-Agent HMAC Signing** — Composite key (`hmac_secret:agent_api_key`), per-agent isolation
5. **CIBA Push Notifications** — Human approval via Guardian app (64-char binding message)
6. **Step-up Authentication** — Automatic model escalation for high-value actions
7. **Scope Creep Detection** — First-time action alerts + 3x amount anomaly detection
8. **FGA Access Control** — Fail-closed when configured, role-based visibility
9. **Credential Encryption at Rest** — Fernet (AES-128-CBC), production refuses plaintext
10. **Multi-tenant Workspace Isolation** — Per-user workspace, X-User-Sub header auth
11. **Circuit Breaker** — Redis-backed, protects against Auth0 downtime cascade
12. **PII Masking** — Emails and names masked in audit logs automatically
13. **Rate Limiting** — Per-agent API key + per-job decision limits
14. **Refresh Token Encryption** — OAuth tokens encrypted at rest, decrypted only at execution
15. **26 Token Vault Providers** — Any Auth0 OAuth connection works out of the box
16. **Per-Step Least Privilege** — Each agent in a chain gets only the tools needed for its specific role (1-2 tools, not the full 15+). Framework-level enforcement, not prompt-level — even prompt injection can't access filtered tools
17. **Cascading Hallucination Prevention** — Chain context passes only verified tool execution results between agents, not LLM-generated text. Prevents Agent A's hallucination from propagating to Agent B
18. **Input Parameter Validation** — SQL injection, shell injection, path traversal, and script injection patterns blocked at framework level before tool execution
19. **Defense-in-Depth Prompt Security** — Security rules repeated across 3 layers (agent prompt, orchestrator, chain context) to prevent LLM instruction drift
20. **Token Exchange Retry with Backoff** — Exponential backoff (500ms, 1s, 2s) on Token Vault server errors; client errors fail immediately
21. **Approval Pattern Analysis** — Learned insights from approval history: high rejection rates, amount anomalies, slow approvals, always-approved connections
22. **Hash-Chained Audit Trail** — Each audit entry includes SHA-256 hash of previous entry, creating tamper-evident chain for SOC2 compliance
23. **Dead Letter Queue** — Failed Celery tasks go to DLQ after max retries instead of being silently dropped
24. **Per-Workspace Circuit Breakers** — Isolate tenant failures so one workspace's Auth0 issues don't affect others
25. **Deep Health Checks** — `/health/deep` verifies DB, Redis, and Ollama connectivity; returns degraded status if any dependency fails
26. **Non-Root Docker** — API container runs as unprivileged user
27. **Connection Health Monitoring** — Verify Token Vault token validity per connection
28. **Time-Boxed Approvals** — Approved actions expire if not executed within configurable window
29. **Per-Rule Budget Limits** — Daily/weekly/monthly spending caps per approval rule
30. **Scheduled Approval Windows** — Restrict approvals to specific days of the week
31. **Re-Authorization Enforcement** — Force fresh approval after N consecutive auto-approves
32. **Risk Score Visualization** — Real-time risk distribution dashboard with per-connection breakdown
33. **Permission Map** — Agent-to-service permission matrix with scope and usage visibility

### Known Limitations

- **MFA + Token Exchange:** Auth0 Token Exchange does not support tenants with MFA enabled on the connected account flow. Workaround: use risk-based MFA rules or disable MFA for service accounts.
- **Ollama GPU:** Local LLM requires NVIDIA GPU for real-time performance. CPU fallback works but is slower. Alternative: use Groq (free tier) for cloud inference.

---

## Dashboard Pages

| Page | Description |
|------|-------------|
| Dashboard | Real-time stats, SSE live feed, pending approvals, security status |
| Connections | 26 services via Token Vault, inline action edit, OAuth connect |
| Rules & Consent | Approval rules with step-up + consent/permissions (tabbed) |
| Approvers | CRUD + Guardian auto-linking + delegation + workspace isolation |
| Audit Log | Filterable event log with PII masking, binding messages, Token Vault receipts |
| Connect Agent | Per-agent API key generation, SDK code snippets, live testing |
| Agents | 10 specialized agents (backend-served) + My Agents tab with scenarios |
| Setup | Full-page onboarding wizard (Auth0 creds + connections), no sidebar |
| Settings | Edit existing workspace credentials (sidebar layout) |
| Compliance | Audit trail with timeline visualization, JSON/CSV export for SOC2 |
| Docs | Full SDK reference, API endpoints, approval models, demo architecture |

**Dark mode** supported across all pages (system preference + manual toggle).

---

## API Reference

73 endpoints across 9 domains. Full OpenAPI docs at `/docs`.

**Core:** `POST /request`, `GET /status/:id`, `POST /test-request`, `POST /jobs/:id/decision`
**Rules:** CRUD + `POST /simulate` (dry-run with risk score)
**Approvers:** CRUD + `GET /link-url` + delegation (workspace-scoped)
**Connections:** CRUD + `PUT /:id` (inline edit) + Connected Accounts flow via Token Vault
**Agents:** CRUD + scenarios + regenerate-key + revoke (workspace-scoped)
**Monitoring:** SSE events, audit log, dashboard stats, CIBA quota, security status, consent
**Workspace:** Setup + credentials (encrypted), per-user isolation via X-User-Sub
**Demo:** `GET /demo/agents` catalog + `POST /demo/seed` (workspace-scoped)

---

## Python SDK

```bash
pip install ./sdk
```

```python
from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(base_url="...", api_key="...", hmac_secret="...")

# Decorator — function body never runs, Token Vault executes
@kit.requires_approval(connection="stripe-prod", action="charge")
def charge(amount, customer):
    pass

# Inline gate
result = kit.gate("github-main", "deploy", {"ref": "main", "env": "production"})

# Async support
@kit.async_requires_approval(connection="stripe-prod", action="charge")
async def async_charge(amount, customer):
    pass
```

---

## Key Insights

1. **Agents should never hold credentials.** The middleware pattern eliminates the largest attack surface in agentic AI.

2. **Step-up authentication makes security proportional to risk.** A $5 charge and a $50,000 wire transfer shouldn't have the same approval flow.

3. **Connected Accounts flow is different from login flow.** Token Exchange requires tokens stored via `/me/v1/connected-accounts`, not `/authorize`. This distinction is critical and not obvious from documentation.

4. **Token Vault supports 27+ providers out of the box.** Any service with an Auth0 OAuth connection works — Stripe, GitHub, Slack, Google, Microsoft, Salesforce, and more. No credential management needed.

5. **Per-agent isolation matters.** Each agent gets its own API key and HMAC signature. Revoking one agent doesn't affect others. Rate limits are per-agent.

6. **Multi-tenant from day one.** Per-user workspace isolation via `X-User-Sub` header. New users get empty state, not someone else's data.

7. **Real-time feedback changes behavior.** SSE live events give immediate visibility into agent actions — fundamentally different from after-the-fact audit logs.

8. **Amount anomaly detection catches scope creep.** If an agent suddenly requests 3x the historical average, it's flagged in the audit trail before the human even reviews it.

---

## Project Status

ApprovalKit is open-source under the MIT license. The project originated at the [Authorized to Act](https://authorizedtoact.devpost.com/) hackathon; the original technical write-up is preserved in [HACKATHON.md](HACKATHON.md). Setup instructions live in [SETUP.md](SETUP.md), and longer-form documentation lives under [`docs/`](docs/).

Contributions, issues, and discussions are welcome.
