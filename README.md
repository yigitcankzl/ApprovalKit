# ApprovalKit

**Human Approval Middleware for AI Agents**

> One decorator. Any agent. Credentials never leave Auth0 Token Vault.

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

Supports 20+ providers: Stripe, GitHub, Google, Slack, Salesforce, Microsoft, Notion, Jira, Discord, Dropbox, Box, Figma, Shopify, HubSpot, Linear, and more.

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
| API | Python 3.11, FastAPI, SQLAlchemy, Pydantic v2 |
| Worker | Celery 5.4, Redis 7 |
| Database | PostgreSQL 16 |
| Frontend | Next.js 14, React 18, Tailwind CSS, TypeScript |
| Auth | Auth0 Token Vault, CIBA, FGA, nextjs-auth0 v4 |
| SDK | Python, pip-installable, sync + async |
| Infrastructure | Docker Compose (6 services) |

---

## Quick Start

```bash
git clone <repo-url> && cd ApprovalKit
docker compose up -d

# Open dashboard — configure Auth0 credentials via UI
open http://localhost:3000/settings

# Or use .env for headless setup
cp .env.example .env && cp frontend/.env.local.example frontend/.env.local
```

### Run the demo agent

```bash
pip install requests
APPROVALKIT_URL=http://localhost:8000 \
APPROVALKIT_API_KEY=<from settings> \
APPROVALKIT_HMAC_SECRET=<from settings> \
python examples/shopping_bot.py
```

The shopping bot charges $349 → Guardian push goes to your phone → approve → Token Vault executes the Stripe charge. The agent never sees the Stripe API key.

---

## TravelOps Agent (Companion Demo)

A complete **corporate travel booking agent** that demonstrates ApprovalKit in a real-world scenario. Available as a separate project:

```
travelops/
├── with-approvalkit/       # Safe: Token Vault, Guardian approval, audit trail
├── without-approvalkit/    # Unsafe: Agent holds API keys, no approval
├── backend/                # Standalone FastAPI dashboard
└── frontend/               # Travel booking UI on port 3001
```

The side-by-side comparison shows why human-in-the-loop approval matters:

| | Without ApprovalKit | With ApprovalKit |
|---|---|---|
| $3200 flight | Charged immediately | Manager + CFO both approve |
| Credentials | Agent holds Stripe key | Agent never sees key |
| Wrong amount | Money gone | Approver catches it |
| Audit trail | None | Full log with timestamps |

---

## Security Model

1. **Token Vault** — Credentials never stored locally, never reach the agent
2. **Token Exchange (RFC 8693)** — Standard-compliant federated token retrieval
3. **Connected Accounts** — Proper Token Vault flow via My Account API
4. **HMAC-SHA256 Request Signing** — Every agent request signed with timestamp (5-min replay window)
5. **CIBA Push Notifications** — Human approval via Guardian app (64-char binding message)
6. **Step-up Authentication** — Automatic model escalation for high-value actions
7. **Scope Creep Detection** — Alerts on first-time agent:action combinations
8. **FGA Access Control** — Role-based visibility (admin, approver, viewer)
9. **Credential Encryption at Rest** — Workspace secrets encrypted with Fernet (AES-128-CBC)
10. **Multi-tenant Isolation** — Each org has its own Auth0 tenant and credentials

---

## Dashboard Pages

| Page | Description |
|------|-------------|
| Dashboard | Real-time stats, SSE live feed, pending approvals, security status |
| Connections | OAuth connect via Token Vault (20+ providers), auto-detection |
| Rules | Approval rules with step-up, expandable cards with Check Rule / Run Live |
| Approvers | CRUD + Guardian auto-linking + delegation |
| Audit Log | Filterable event log with binding messages and Token Vault receipts |
| Consent | Per-service permissions, scopes, recent access, revoke |
| Agent Demos | 7 pre-built agent scenarios with interactive flow diagrams |
| Settings | Auth0/FGA credentials via dashboard (no .env needed) |
| Docs | Full SDK reference, API endpoints, approval models |

---

## API Reference

36 endpoints across 7 domains. Full OpenAPI docs at `/docs`.

**Core:** `POST /request`, `GET /status/:id`, `POST /test-request`
**Rules:** CRUD + `POST /simulate`
**Approvers:** CRUD + `GET /link-url` + delegation
**Connections:** CRUD + Connected Accounts flow + OAuth callback
**Monitoring:** SSE events, audit log, dashboard stats, security status, consent
**Workspace:** Setup with encrypted credential storage

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

4. **Management API is a valid fallback.** Not all providers support refresh tokens (GitHub doesn't). Graceful degradation ensures universal compatibility.

5. **Credentials belong in the database, not .env files.** Multi-tenancy requires per-org credential storage with encryption at rest.

6. **Real-time feedback changes behavior.** SSE live events give immediate visibility into agent actions — fundamentally different from after-the-fact audit logs.

---

## Blog Post: Building Token Vault Token Exchange for AI Agent Approval

### The Discovery

When we started building ApprovalKit, we assumed Token Vault was simple: store OAuth tokens, retrieve them when needed. We were wrong.

Our first implementation used the Auth0 Management API (`GET /api/v2/users/{id}`) to read `identities[].access_token`. This worked for GitHub (which uses long-lived tokens), but it was the wrong approach. Management API requires broad permissions, doesn't auto-refresh tokens, and isn't the recommended pattern.

The proper approach is **Token Exchange (RFC 8693)**: exchange an Auth0 refresh token for a fresh external provider access token. But this required a discovery that cost us significant debugging time.

### The Login Flow vs Connected Accounts Flow

When a user authorizes a social connection via Auth0's standard `/authorize` endpoint, tokens are stored in the `identities[]` array on the user profile. Token Exchange **cannot access these tokens**.

For Token Exchange to work, tokens must be stored via the **Connected Accounts** flow using Auth0's My Account API:

```
POST /me/v1/connected-accounts/connect
→ user authorizes external service
POST /me/v1/connected-accounts/complete
→ tokens stored in connected_accounts[] (Token Vault)
```

This flow requires:
- `oidc_conformant: true` on the application
- Token Vault grant type explicitly enabled
- MFA policy set to "Never" (Token Exchange doesn't support MFA)
- `create:me:connected_accounts` scope via My Account API

None of this was immediately obvious from the documentation. We discovered it through trial and error with the `federated_connection_refresh_token_not_found` error.

### The Architecture

Our final Token Vault integration has two paths:

**Primary (Token Exchange):** For providers that support refresh tokens (Stripe, Google, Salesforce). The user connects via Connected Accounts flow, Auth0 stores the federated refresh token, and Token Exchange retrieves fresh access tokens at execution time.

**Fallback (Management API):** For providers like GitHub that issue long-lived access tokens without refresh tokens. The Management API reads the token directly from the user's identity profile.

This dual approach ensures ApprovalKit works with **any** OAuth provider while using the most secure method available.

### The Insight

The biggest insight from building with Token Vault: **the boundary between "login" and "connected account" is the most important architectural decision**. Getting this wrong means your Token Exchange calls silently fail. Getting it right means your AI agents can securely execute actions across 20+ services without ever holding a credential.

For the Auth0 team: clearer documentation on the Connected Accounts flow prerequisites would save developers significant time. The `federated_connection_refresh_token_not_found` error could include a hint about which flow was used to store the token.

---

*Built for the Authorized to Act hackathon. ApprovalKit is open source.*
