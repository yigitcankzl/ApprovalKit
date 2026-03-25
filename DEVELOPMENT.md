# ApprovalKit — Development Journey & Architecture

## What is ApprovalKit?

ApprovalKit is a **human approval middleware for AI agents**. When an AI agent needs to perform a high-stakes action — charging a credit card, deploying code, sending an email — it doesn't execute directly. Instead, a human approves it first via a push notification on their phone, and the platform executes the action server-side. **The agent never sees or holds any credentials.**

One decorator. Any agent. Any action.

```python
from approvalkit import ApprovalKit

kit = ApprovalKit(base_url="http://localhost:8000", api_key="...", hmac_secret="...")

@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    pass  # Body never runs — Token Vault executes server-side

charge_customer(349, "alice@example.com")
# → Guardian push sent to approver's phone
# → Human taps Approve
# → Auth0 Token Vault retrieves Stripe token and executes the charge
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌───────────────┐
│  AI Agent    │────▶│ ApprovalKit  │────▶│  Auth0 CIBA     │────▶│    Human      │
│  (any LLM)  │     │  API + SDK   │     │  Guardian Push   │     │  (phone app)  │
└─────────────┘     └──────────────┘     └─────────────────┘     └───────┬───────┘
                           │                                             │
                           │                                      Approve/Deny
                           │                                             │
                    ┌──────▼──────┐     ┌─────────────────┐     ┌───────▼───────┐
                    │ Rule Engine │     │  Target Service  │◀────│ Auth0 Token   │
                    │ Step-up     │     │  (Stripe, GitHub)│     │ Vault (RFC    │
                    │ Conditions  │     └─────────────────┘     │ 8693 Exchange)│
                    └─────────────┘                             └───────────────┘
```

### Core Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API | FastAPI + PostgreSQL | Rule engine, job management, audit logging |
| Worker | Celery + Redis | Async CIBA polling, Token Vault execution |
| Frontend | Next.js 14 | Dashboard, rule builder, consent page, docs |
| SDK | Python (pip install) | `@requires_approval` decorator for agents |
| Auth0 Token Vault | RFC 8693 Token Exchange | Secure credential storage & execution |
| Auth0 CIBA | Guardian Push | Human-in-the-loop approval notifications |
| Auth0 FGA | OpenFGA | Fine-grained access control for platform |

---

## Development Timeline & Key Decisions

### Phase 1: Core Platform

**Initial architecture** — FastAPI backend with PostgreSQL, Celery workers for async processing, Redis for message broker.

**Rule engine** — Flexible condition-based rules with 9 operators (`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`). Rules match on `connection:action` pairs with optional parameter conditions. Priority-based matching — first match wins.

**5 approval models** — Different workflows for different risk levels:
- `any_one` — First approval from any approver
- `specific` — Only a designated person
- `all_of_n` — Everyone must approve
- `k_of_n` — Quorum (k of n approvers within time window)
- `sequential` — Ordered chain, each step must approve

**CIBA integration** — Auth0 Client-Initiated Backchannel Authentication sends push notifications to approvers' phones via Guardian app. The worker polls Auth0's token endpoint until the user approves, rejects, or times out.

### Phase 2: Token Vault Evolution

**Decision: Remove Fernet encryption, move to Auth0 Token Vault.**

Initially, we stored encrypted credentials locally using Fernet symmetric encryption. This was a security risk — credentials lived in our database, and the agent could potentially access them.

We replaced this entirely with Auth0 Token Vault. Now:
- User connects their service account (Stripe, GitHub) via OAuth
- Auth0 stores the OAuth tokens in Token Vault
- When an action is approved, the platform retrieves the token via Token Vault and executes the action
- The agent never sees the token

**Token Exchange (RFC 8693) vs Management API:**

Our first Token Vault implementation used the Auth0 Management API (`GET /api/v2/users/{id}`) to read `identities[].access_token`. This worked but was suboptimal:
- Required broad Management API permissions
- No automatic token refresh
- Not the recommended approach

We migrated to **Token Vault Token Exchange** — the proper way:
```
POST /oauth/token
grant_type=urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token
subject_token={auth0_refresh_token}
connection={provider_name}
```

This required discovering that the standard `/authorize` login flow stores tokens in `identities[]`, which Token Exchange cannot access. We had to implement the **Connected Accounts flow** using Auth0's My Account API (`/me/v1/connected-accounts/connect` + `/complete`), which stores tokens in `connected_accounts[]` where Token Exchange can find them.

**Key learning:** Token Exchange requires Connected Accounts flow, not login flow. The auth0 refresh token from the user's login session is the `subject_token`, and Auth0 internally looks up the external provider's refresh token from the connected accounts store.

### Phase 3: Connected Accounts Flow

The Connected Accounts flow is a two-step process:

1. **Initiate**: `POST /me/v1/connected-accounts/connect` with the user's access token → returns a `connect_uri` with a ticket
2. **Complete**: After the user authorizes the external service, `POST /me/v1/connected-accounts/complete` with the `connect_code` → Auth0 stores the external provider's refresh token in Token Vault

Prerequisites we discovered:
- Application must have `oidc_conformant: true`
- Token Vault grant type must be enabled on the application
- MFA policy must be set to "Never" (Token Exchange doesn't support MFA)
- The application needs `create:me:connected_accounts` scope via My Account API
- Connected Accounts redirect URI must be whitelisted separately

The Management API fallback remains for providers like GitHub that don't issue refresh tokens (GitHub uses long-lived access tokens).

### Phase 4: Frontend Dashboard & Real-time Features

**SSE Live Feed** — Server-Sent Events via Redis pub/sub. Every job state change (requested, approved, rejected, timeout) is published to a Redis channel. The frontend subscribes via `EventSource` and shows events in real-time.

**Pending Approvals Panel** — Shows jobs waiting for Guardian approval with their parameters. Initially had Approve/Reject/Edit buttons, but we removed them because:
- The whole point is phone-based approval (Guardian push)
- Web approval bypasses the security model
- The panel is purely informational — showing what's pending

**Trust Chain Visualization** — Each rule card shows the approval chain:
```
stripe-prod:charge → [CEO] → [CFO] → Auth0 Token Vault
```

### Phase 5: Step-up Authentication

**Decision: Add automatic approval model escalation for high-value actions.**

The hackathon judges explicitly ask: *"Are high-stakes actions identified and protected, and is step-up authentication used where it matters?"*

We added `step_up_model` and `step_up_conditions` to rules. When a request matches a rule AND the step-up conditions are met, the approval model automatically escalates:

```
Rule: stripe-prod:charge
  Normal: any_one (one approver)
  Step-up condition: amount >= 1000
  Step-up model: all_of_n (ALL approvers must approve)

$349 charge → any_one → single Guardian push → approved
$5000 charge → step-up triggered → all_of_n → ALL approvers get push → all must approve
```

The step-up evaluation happens in the Celery worker before dispatching to the model processor. An audit event (`step_up`) is logged and published via SSE.

### Phase 6: Auth0 Login + Consent Page

**Auth0 Login** — Added `@auth0/nextjs-auth0` v4 SDK. Uses middleware approach (not route handlers). The sidebar shows user profile when logged in and a "Login with Auth0" button when not.

**Consent & Permissions Page** — A centralized view answering "What can agents access?":
- Per-service cards showing connected user, OAuth scopes, allowed actions
- Rules governing each service with step-up indicators
- Recent agent access history
- Revoke button to disconnect a service from Token Vault

### Phase 7: Approver Guardian Auto-Linking

**Decision: Remove manual auth0_user_id entry.**

Initially, approvers required manually entering their Auth0 user ID. This was error-prone and confusing. We added a "Link Account" flow:

1. Admin creates approver (name + email only)
2. Clicks "Link Account" on the approver card
3. Redirects to Auth0 login
4. After login, the `sub` (e.g., `github|111859800`) is saved automatically
5. Guardian push notifications now go to the right person

### Phase 8: Multi-tenant — Credentials from DB, not .env

**Decision: Move Auth0/FGA credentials from environment variables to the database.**

Previously, all Auth0 credentials (`AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, etc.) and FGA credentials lived in `.env` files. This meant:
- Only one organization per deployment
- Server restart required to change credentials
- Manual file editing for new orgs

We added 14 credential columns to the `workspaces` table. Each organization stores its own:
- Auth0 M2M client (for CIBA, Management API)
- Auth0 Web client (for Token Exchange, Connected Accounts)
- FGA store and client credentials
- Encryption key for local secrets

**The onboarding flow now collects all credentials via the dashboard UI** — no `.env` editing needed. A new organization:
1. Opens `/onboarding`
2. Enters Auth0 domain, M2M client ID/secret, Web client ID/secret
3. Optionally enters FGA credentials
4. Clicks "Connect" — platform validates Auth0 connectivity and saves to DB
5. Gets API key + HMAC secret for their agents

**Encryption at rest:** All client secrets are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) before storage. The encryption key is derived from the platform's `CREDENTIALS_KEY`. Secrets are transparently decrypted when read via the `WorkspaceConfig` helper.

**Fallback chain:** `DB workspace value → .env global value → empty string`. This ensures backward compatibility — existing deployments with `.env` config continue working without migration.

```python
# api/services/workspace_config.py
async def get_workspace_config(workspace_id, db) -> WorkspaceConfig:
    ws = await db.get(Workspace, workspace_id)
    return WorkspaceConfig(
        auth0_domain=ws.auth0_domain or settings.AUTH0_DOMAIN,
        auth0_client_secret=decrypt_secret(ws.auth0_m2m_client_secret) or settings.AUTH0_CLIENT_SECRET,
        # ... DB first, .env fallback for every field
    )
```

---

## Auth0 Integration Summary

### Token Vault
- **Connected Accounts flow** for Stripe (external provider refresh token stored in Token Vault)
- **Token Exchange (RFC 8693)** retrieves fresh external access tokens at execution time
- **Management API fallback** for GitHub (long-lived tokens, no refresh token)
- Agent NEVER sees credentials — the platform executes actions server-side

### CIBA (Client-Initiated Backchannel Authentication)
- Push notifications via Auth0 Guardian app
- `binding_message` shows action context on the phone (max 64 chars per spec)
- Polling with exponential backoff (handles `authorization_pending`, `slow_down`, `429`)
- 300-second timeout per approval request

### FGA (Fine-Grained Authorization)
- Role-based access: `admin`, `approver`, `agent_owner`, `viewer`
- Admins see all audit logs; approvers see only their own
- Rule read/write permissions enforced per role
- FGA store and model configured via setup script

### Auth0 Login
- `@auth0/nextjs-auth0` v4 SDK with middleware approach
- `Auth0Provider` wraps the app layout
- Session-based authentication with refresh tokens
- `offline_access` scope for persistent sessions

---

## API Endpoints (36 total)

### Approval Flow
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/request` | Submit approval request (agent calls this) |
| GET | `/api/v1/status/{job_id}` | Poll job status |
| PATCH | `/api/v1/jobs/{job_id}/params` | Modify params (partial approval) |
| GET | `/api/v1/jobs/pending` | List pending jobs |
| POST | `/api/v1/jobs/{job_id}/decision` | Web-based decision |

### Rules
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/rules` | Create rule with step-up config |
| GET | `/api/v1/rules` | List all rules |
| GET | `/api/v1/rules/{id}` | Get rule details |
| PUT | `/api/v1/rules/{id}` | Update rule |
| DELETE | `/api/v1/rules/{id}` | Deactivate rule |
| POST | `/api/v1/rules/simulate` | Test rule matching + step-up |

### Approvers
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/approvers` | Create approver |
| GET | `/api/v1/approvers` | List approvers |
| GET | `/api/v1/approvers/{id}` | Get approver |
| PUT | `/api/v1/approvers/{id}` | Update approver |
| DELETE | `/api/v1/approvers/{id}` | Delete approver |
| GET | `/api/v1/approvers/{id}/link-url` | Auth0 link URL |
| GET | `/api/v1/approvers/link-callback` | Link callback |
| PUT | `/api/v1/approvers/{id}/delegate` | Set delegation |
| DELETE | `/api/v1/approvers/{id}/delegate` | Remove delegation |

### Connections
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/connections` | Create connection |
| GET | `/api/v1/connections` | List (with Auth0 detection) |
| GET | `/api/v1/connections/{id}` | Get connection |
| GET | `/api/v1/connections/{id}/connect-url` | Connected Accounts flow |
| DELETE | `/api/v1/connections/{id}/auth` | Disconnect |
| GET | `/api/v1/connections/oauth/callback` | OAuth callback (fallback) |
| GET | `/api/v1/connections/connected-accounts/callback` | Connected Accounts callback |

### Monitoring
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/events` | SSE live event stream |
| GET | `/api/v1/audit` | Audit log (FGA-filtered) |
| GET | `/api/v1/dashboard` | Dashboard stats |
| GET | `/api/v1/ciba-quota` | CIBA usage info |
| GET | `/api/v1/security-status` | Security layer status |
| GET | `/api/v1/consent` | Consent & permissions view |

### Workspace
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/workspace/setup` | Create workspace or update credentials |
| GET | `/api/v1/workspace` | Get workspace info (no secrets exposed) |

---

## Frontend Pages (14 total)

| Page | Path | Description |
|------|------|-------------|
| Landing | `/` | Hero, architecture diagram, code snippet, CTA |
| Dashboard | `/dashboard` | Stats, live SSE feed, pending approvals, security status |
| Connections | `/connections` | OAuth connect via Token Vault, dynamic Auth0 detection |
| Rules List | `/rules` | All rules with trust chain + step-up badges |
| New Rule | `/rules/new` | Full rule builder with step-up config |
| Rule Detail | `/rules/[id]` | Rule details view |
| Edit Rule | `/rules/[id]/edit` | Edit with step-up support |
| Approvers | `/approvers` | CRUD + Guardian auto-linking + delegation |
| Audit Log | `/audit` | Filterable event log with binding messages |
| Consent | `/consent` | Per-service permissions, scopes, revoke |
| Simulate | `/simulate` | Test rule matching with step-up result |
| Use Cases | `/gallery` | Feature showcase |
| Onboarding | `/onboarding` | 3-step setup wizard with Auth0/FGA credential form |
| Docs | `/docs` | Full SDK reference with 9 sections |

---

## Security Features

1. **Token Vault** — Credentials never stored locally, never reach the agent
2. **Token Exchange (RFC 8693)** — Standard-compliant token retrieval
3. **HMAC-SHA256 Request Signing** — Every agent request is signed with timestamp
4. **CIBA Push Notifications** — Human approval via Guardian app
5. **Step-up Authentication** — Automatic escalation for high-value actions
6. **Scope Creep Detection** — Alerts when agent accesses new action types
7. **FGA Access Control** — Role-based visibility (admin, approver, viewer)
8. **Blackout Windows** — Block approvals during maintenance periods
9. **Cooldown Limits** — Rate limiting per rule
10. **Delegation** — Approvers can delegate to others with time bounds
11. **Credential Encryption at Rest** — Workspace secrets encrypted with Fernet (AES-128-CBC) before DB storage
12. **Multi-tenant Isolation** — Each workspace has its own Auth0 tenant, FGA store, and credentials

---

## How to Run

```bash
# 1. Clone and start
git clone https://github.com/yourusername/ApprovalKit.git
cd ApprovalKit
docker compose up -d

# 2. Open dashboard and complete onboarding
open http://localhost:3000/onboarding
# → Enter Auth0 domain, M2M client ID/secret, Web client ID/secret
# → Enter FGA credentials (optional)
# → Platform validates and saves to DB
# → Creates API key + HMAC secret for agents

# 3. Login and configure
# → Login with Auth0 (sidebar button)
# → Connect services (Connections page)
# → Add approvers and link their Guardian accounts
# → Create approval rules

# 4. Run shopping bot demo
pip install requests
APPROVALKIT_URL=http://localhost:8000 \
APPROVALKIT_API_KEY=<from onboarding> \
APPROVALKIT_HMAC_SECRET=<from onboarding> \
python examples/shopping_bot.py
```

> **Note:** No `.env` file editing required for Auth0/FGA credentials. Everything is configured through the dashboard. A minimal `.env` with just `DATABASE_URL`, `REDIS_URL`, and `CREDENTIALS_KEY` is needed for the platform itself.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| Worker | Celery 5.4, Redis 7 |
| Database | PostgreSQL 16 |
| Frontend | Next.js 14, React 18, Tailwind CSS, TypeScript |
| Auth | Auth0 (Token Vault, CIBA, FGA, nextjs-auth0 v4) |
| SDK | Python, pip-installable, zero heavy dependencies |
| Infrastructure | Docker Compose (6 services) |

---

## Key Insights for Agent Authorization

1. **Agents should never hold credentials.** The middleware pattern (agent requests → human approves → platform executes) eliminates the largest attack surface.

2. **Step-up authentication is essential.** A $5 charge and a $50,000 charge shouldn't have the same approval requirements. Dynamic model escalation based on parameters makes security proportional to risk.

3. **Connected Accounts flow is different from login flow.** Auth0's Token Exchange requires tokens stored via the Connected Accounts API (`/me/v1/connected-accounts`), not the standard `/authorize` endpoint. This is a crucial distinction that isn't immediately obvious from the documentation.

4. **CIBA binding messages need to be meaningful but brief.** The 64-character limit forces you to think carefully about what context the approver needs to make a decision. "Charge $349 alice@ex" is better than a JSON dump.

5. **Management API is a valid fallback.** Not all providers support refresh tokens (GitHub doesn't). A graceful fallback to the Management API ensures the system works universally while using Token Exchange where possible.

6. **Real-time feedback changes behavior.** SSE live events and pending approval panels give administrators immediate visibility into agent actions, which is fundamentally different from after-the-fact audit logs.

7. **Credentials belong in the database, not in environment files.** Moving Auth0/FGA credentials from `.env` to the workspace table enables true multi-tenancy. Each organization configures its own Auth0 tenant through the dashboard UI. Secrets are encrypted at rest with Fernet. The `.env` serves only as a fallback for the platform's own infrastructure config (database URL, Redis, encryption key).
