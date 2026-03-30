# ApprovalKit

[![Auth0 Token Vault](https://img.shields.io/badge/Auth0-Token%20Vault-blue?logo=auth0)](https://auth0.com/ai/docs/intro/token-vault)
[![Python SDK](https://img.shields.io/badge/SDK-Python-green?logo=python)](sdk/)
[![MCP Server](https://img.shields.io/badge/MCP-Compatible-purple)](sdk/approvalkit/mcp_server.py)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](docker-compose.yml)
[![30 Services](https://img.shields.io/badge/Services-30%20Handlers-orange)](api/services/token_vault.py)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**Human Approval Middleware for AI Agents**

> One decorator. Any agent. Credentials never leave Auth0 Token Vault.

```
pip install ./sdk
```

```python
@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount, email):
    pass  # Token Vault executes — agent never sees credentials
```

Works with **LangChain**, **CrewAI**, **OpenAI Function Calling**, **Claude MCP**, or any Python agent.

---

## The Problem

AI agents are increasingly autonomous — they can book flights, deploy code, charge credit cards, send emails. But **what happens when they make a mistake?** A wrong Stripe charge, an accidental production deploy, or an unauthorized email can't be undone.

Today, most agents hold raw API keys in memory. If the agent is compromised, or if it hallucinates, there's no safety net. No human reviews the action. No audit trail exists.

## The Solution

ApprovalKit is a **plug-and-play middleware** that sits between AI agents and the services they control. When an agent wants to take a high-stakes action, ApprovalKit:

1. **Evaluates the request** against configurable rules
2. **Sends a push notification** to the right human (via Auth0 CIBA + Guardian)
3. **Waits for approval** on the human's phone
4. **Executes the action** through Auth0 Token Vault — the agent never sees the credentials

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

kit = ApprovalKit(base_url="...", api_key="...", hmac_secret="...")

@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    pass  # Body never runs — Token Vault executes server-side
```

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

All actions execute through **Auth0 Token Vault** — the agent never sees credentials. Token Vault supports 27+ OAuth providers:

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

ApprovalKit has **30 built-in service handlers** covering every Token Vault provider — Stripe, GitHub, Slack, Google (Gmail/Calendar/Drive/Sheets), Microsoft (Outlook/OneDrive), Salesforce, Notion, Jira, Discord, Linear, HubSpot, Shopify, PayPal, Dropbox, Box, Bitbucket, Figma, Spotify, Twitch, Fitbit, Freshbooks, DigitalOcean, Basecamp, Hugging Face, Amadeus.

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

### 5 Approval Models

| Model | How it works |
|-------|-------------|
| `any_one` | First approval from any listed approver |
| `specific` | Only the designated person can approve |
| `all_of_n` | Every approver must approve |
| `k_of_n` | k out of n within a quorum time window |
| `sequential` | Ordered chain — each step waits for the previous |

### Consent & Permissions

A centralized page shows what agents can access, which services are connected, OAuth scopes granted, and allows instant revocation.

### Multi-tenant

Each organization stores its own Auth0 and FGA credentials in the database (encrypted at rest with Fernet). No `.env` editing — everything configured through the dashboard.

### Real-time Dashboard

SSE live feed via Redis pub/sub shows approval events as they happen. Pending approvals panel, CIBA quota tracking, security status monitoring.

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
| Database | PostgreSQL 16, 8 migrations, Fernet encryption at rest |
| Frontend | Next.js 14, React 18, Tailwind CSS, TypeScript, dark mode |
| Auth | Auth0 Token Vault, CIBA, FGA, nextjs-auth0 v4, per-agent HMAC |
| SDK | Python, pip-installable, sync + async, jitter polling |
| Execution | 30 built-in handlers, all via Auth0 Token Vault |
| Infrastructure | Docker Compose (8 services), Ollama GPU support, Healthcare companion demo |

---

## Quick Start

```bash
git clone https://github.com/yigitcankzl/ApprovalKit.git
cd ApprovalKit
chmod +x setup.sh
./setup.sh
```

This starts all services (PostgreSQL, Redis, Vault, Ollama, API, Worker, Frontend), downloads the AI model, and seeds demo data. Open `http://localhost:3000` and start using the demo agents.

**For detailed setup instructions, Auth0 configuration, and using your own tenant, see [SETUP.md](SETUP.md).**

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
15. **27+ Token Vault Providers** — Any Auth0 OAuth connection works out of the box

---

## Dashboard Pages

| Page | Description |
|------|-------------|
| Dashboard | Real-time stats, SSE live feed, pending approvals, security status |
| Connections | 27+ services via Token Vault, inline action edit, OAuth connect |
| Rules | Approval rules with step-up, expandable cards with Check Rule / Run Live |
| Approvers | CRUD + Guardian auto-linking + delegation + workspace isolation |
| Audit Log | Filterable event log with PII masking, binding messages, Token Vault receipts |
| Connect Agent | Per-agent API key generation, SDK code snippets, live testing |
| Agents | 12 demo agents (backend-served) + My Agents tab with scenarios |
| Setup | Full-page onboarding wizard (Auth0 creds + connections), no sidebar |
| Settings | Edit existing workspace credentials (sidebar layout) |
| Docs | Full SDK reference, API endpoints, approval models |

**Dark mode** supported across all pages (system preference + manual toggle).

---

## API Reference

40+ endpoints across 8 domains. Full OpenAPI docs at `/docs`.

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

*Built for the [Authorized to Act](https://authorizedtoact.devpost.com/) hackathon. See [BLOG_POST.md](BLOG_POST.md) for our Token Vault deep-dive and [SETUP.md](SETUP.md) for installation guide.*
