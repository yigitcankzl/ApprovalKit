# ApprovalKit — Setup Guide

## Quick Start (Demo Mode)

```bash
git clone https://github.com/yigitcankzl/ApprovalKit.git
cd ApprovalKit
chmod +x setup.sh
./setup.sh
```

This starts all services with the pre-configured Auth0 tenant. Open `http://localhost:3000`, log in, and start using the demo agents.

---

## Prerequisites

- **Docker** & **Docker Compose V2**
- **~10 GB disk** (Docker images + Ollama model)
- **NVIDIA GPU** recommended for fast LLM responses (CPU fallback works but slower)

---

## Architecture

```
./setup.sh starts these services:

┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│PostgreSQL│  │  Redis   │  │  Vault   │  │  Ollama  │
│  :5432   │  │  :6379   │  │  :8200   │  │  :11434  │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │              │
     └──────┬──────┴─────────────┘              │
            │                                   │
     ┌──────┴──────┐  ┌──────────┐             │
     │  FastAPI    │  │  Celery  │             │
     │  API :8000  │  │  Worker  │             │
     └──────┬──────┘  └──────────┘             │
            │                                   │
     ┌──────┴──────────────────────────────────┘
     │
     ┌──────┴──────┐
     │   Next.js   │
     │  App :3000  │
     └─────────────┘
```

---

## Using Your Own Auth0 Tenant

If you want to use your own Auth0 account instead of the demo tenant, follow these steps carefully. Every step is critical — missing one will cause silent failures.

### Step 1: Create Auth0 Tenant

1. Sign up at [auth0.com](https://auth0.com) (free tier works)
2. Create a new tenant (e.g., `approvalkit-dev`)
3. Note your **tenant domain**: `your-tenant.us.auth0.com`

### Step 2: Enable Auth0 for AI Agents (Token Vault)

This is the most important step — without it, Token Exchange won't work.

1. Go to **Auth0 Dashboard → Auth0 for AI Agents** (left sidebar, under "AI")
   - If you don't see this menu, go to **Settings → Features → Token Vault** and enable it
2. Enable **Token Vault** for your tenant
3. Note: Token Vault is separate from regular OAuth — it stores tokens via the **Connected Accounts** flow, not the login flow

> **Critical:** Token Exchange (RFC 8693) can ONLY access tokens stored via Connected Accounts (`/me/v1/connected-accounts`). Tokens from standard `/authorize` login are in `identities[]` and cannot be exchanged. This is the #1 source of integration errors.

### Step 3: Create Backend M2M Application

1. **Applications → Create Application → Machine to Machine**
2. Name: `ApprovalKit Backend`
3. **Authorize for Auth0 Management API** with these scopes:
   ```
   read:users
   read:user_idp_tokens
   read:connections
   read:users_app_metadata
   update:users_app_metadata
   ```
4. **Settings → Advanced Settings → Grant Types**, ensure enabled:
   - `Client Credentials`
5. Copy **Client ID** and **Client Secret**

### Step 4: Create Frontend Web Application

1. **Applications → Create Application → Regular Web Application**
2. Name: `ApprovalKit Web`
3. **Settings tab:**
   - **Allowed Callback URLs:**
     ```
     http://localhost:3000/api/auth/callback
     ```
   - **Allowed Logout URLs:**
     ```
     http://localhost:3000
     ```
   - **Allowed Web Origins:**
     ```
     http://localhost:3000
     ```
4. **Settings → Advanced Settings → Grant Types**, enable ALL of these:
   - `Authorization Code`
   - `Refresh Token`
   - `Client Credentials`
   - `Token Exchange` (for Token Vault — critical!)
5. **Settings → Advanced Settings → OAuth:**
   - `OIDC Conformant`: **ON** (required for Token Vault)
   - `Trust Token Endpoint IP Header`: **OFF**
6. Copy **Client ID** and **Client Secret**

### Step 5: Set MFA Policy

Token Exchange does NOT support MFA. If MFA is enabled, Token Vault calls will fail silently.

1. **Security → Multi-factor Authentication**
2. Set **Policy** to **Never** (or create a rule to skip MFA for Token Exchange)

### Step 6: Configure Social Connections

For each service you want agents to control:

#### A. Stripe

1. [Stripe Dashboard → Developers → OAuth](https://dashboard.stripe.com/settings/connect) → Create OAuth app
2. Set redirect URI: `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Auth0: **Authentication → Social → Create Connection → Stripe**
4. Enter Stripe Client ID + Secret
5. **Important:** Toggle **"Token Vault"** ON for this connection
6. Under **Permissions**, add scopes: `read_write`

#### B. Google (Gmail, Calendar, Drive, Sheets)

1. [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials → Create OAuth Client
2. Set authorized redirect URI: `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Enable these APIs in Google Cloud Console:
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Google Sheets API
4. Auth0: **Authentication → Social → Google** → enter Client ID + Secret
5. Under **Permissions**, add scopes:
   ```
   email profile
   https://www.googleapis.com/auth/gmail.send
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/calendar.events
   https://www.googleapis.com/auth/drive
   https://www.googleapis.com/auth/spreadsheets
   ```
6. **Critical — Upstream Params** (for refresh tokens):
   - Go to connection settings → Advanced
   - Add upstream parameter: `access_type` = `offline`
   - Without this, Google won't return a refresh token and Token Exchange will fail
7. Toggle **"Token Vault"** ON

#### C. GitHub

1. [GitHub → Settings → Developer Settings → OAuth Apps](https://github.com/settings/developers) → New OAuth App
2. Authorization callback URL: `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Auth0: **Authentication → Social → GitHub** → enter Client ID + Secret
4. Under **Permissions**, add scope: `repo,workflow`
5. Toggle **"Token Vault"** ON

> Note: GitHub uses long-lived access tokens (no refresh token). Token Exchange works but falls back to Management API for token retrieval.

#### D. Slack

1. [Slack API → Create New App](https://api.slack.com/apps) → From scratch
2. Under **OAuth & Permissions → Redirect URLs**, add: `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Under **Scopes → Bot Token Scopes**, add: `chat:write`, `channels:read`
4. Install app to your workspace
5. Auth0: **Authentication → Social → Create Connection → Custom Social**
   - Authorization URL: `https://slack.com/oauth/v2/authorize`
   - Token URL: `https://slack.com/api/oauth.v2.access`
   - Scope: `chat:write channels:read`
   - Enter Client ID + Client Secret from Slack app
6. Toggle **"Token Vault"** ON

#### E. Other Services (Discord, PayPal, Figma, etc.)

Auth0 Token Vault supports 27+ OAuth providers. For any service:

1. Create OAuth app on the service's developer portal
2. Set redirect URI to `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Auth0: **Authentication → Social → Create Connection**
4. Enter Client ID + Secret
5. Toggle **"Token Vault"** ON
6. Ensure the connection requests `offline_access` or equivalent for refresh tokens

See [Auth0 Token Vault Integrations](https://auth0.com/ai/docs/intro/integrations) for the full list.

### Step 7: Connected Accounts Redirect URI

ApprovalKit uses the Connected Accounts flow to store tokens in Token Vault. The redirect URI for this flow must be whitelisted:

1. **Auth0 Dashboard → Applications → Your Web App → Settings**
2. Under **Allowed Callback URLs**, add BOTH:
   ```
   http://localhost:3000/api/auth/callback
   http://localhost:8000/api/v1/connections/connected-accounts/callback
   ```
3. Under **Allowed Web Origins**, add:
   ```
   http://localhost:3000
   http://localhost:8000
   ```

> The Connected Accounts flow works differently from login. It calls `/me/v1/connected-accounts/connect` to get a `connect_uri`, then the user authorizes the external service, and `/me/v1/connected-accounts/complete` stores the refresh token in Token Vault.

### Step 8: Configure FGA (Optional)

Fine-Grained Authorization adds role-based access control (admin/approver/viewer). Skip this for basic demos.

1. Go to [FGA Dashboard](https://dashboard.fga.dev)
2. Create a new store → copy **Store ID**
3. Create authorization model (use `fga/model.fga` from this repo) → copy **Model ID**
4. **Settings → API Credentials** → Create M2M credentials → copy **Client ID** + **Client Secret**
5. If FGA is not configured, all authorization checks pass (allow-all) — the app works but without RBAC

### Step 9: Configure CIBA / Guardian (Optional)

For push notification approvals to mobile phones (instead of web dashboard):

1. Auth0 Dashboard → **Security → Multi-factor Auth → Push via Auth0 Guardian**
2. Enable Guardian push notifications
3. Each approver needs to:
   - Download **Auth0 Guardian** app ([iOS](https://apps.apple.com/app/auth0-guardian/id1093447833) / [Android](https://play.google.com/store/apps/details?id=com.auth0.guardian))
   - Link their Auth0 account via the ApprovalKit Approvers page → "Link Guardian"
4. CIBA push notifications are sent when an approval is pending — approver taps Approve/Deny on their phone

> Without Guardian, approvals happen via the web dashboard (ApprovalKit Approve/Reject buttons). Guardian adds mobile push notifications as an additional channel.

### Step 10: Update Environment Files

Edit `.env`:
```bash
# Auth0 (REQUIRED)
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your-m2m-client-id
AUTH0_CLIENT_SECRET=your-m2m-client-secret
AUTH0_WEB_CLIENT_ID=your-web-client-id
AUTH0_WEB_CLIENT_SECRET=your-web-client-secret
AUTH0_AUDIENCE=https://your-tenant.us.auth0.com/me/
AUTH0_MGMT_API_AUDIENCE=https://your-tenant.us.auth0.com/api/v2/

# FGA (optional — skip if not using RBAC)
FGA_API_URL=https://api.us1.fga.dev
FGA_STORE_ID=your-store-id
FGA_MODEL_ID=your-model-id
FGA_CLIENT_ID=your-fga-client-id
FGA_CLIENT_SECRET=your-fga-client-secret

# Security
HMAC_SECRET=generate-a-random-64-char-hex-string
CREDENTIALS_KEY=generate-a-fernet-key
```

Edit `frontend/.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
AUTH0_SECRET=generate-a-random-32-byte-hex-string
AUTH0_BASE_URL=http://localhost:3000
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your-web-client-id
AUTH0_CLIENT_SECRET=your-web-client-secret
APP_BASE_URL=http://localhost:3000
```

Generate secrets:
```bash
# HMAC_SECRET
python3 -c "import secrets; print(secrets.token_hex(32))"

# CREDENTIALS_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# AUTH0_SECRET
python3 -c "import secrets; print(secrets.token_hex(16))"
```

### Step 11: Start

```bash
./setup.sh
```

### Step 12: Connect Services (After First Login)

After the app is running and you've logged in + completed the Setup Wizard:

1. Go to **Connections** page (`http://localhost:3000/connections`)
2. For each service (Stripe, Google, GitHub, Slack), click **"Connect"**
3. This triggers the **Connected Accounts flow** — you authorize the service, and Auth0 stores the refresh token in Token Vault
4. After connecting, the agent can execute actions on that service via Token Vault — the agent never sees the OAuth token

> **Troubleshooting:** If "Connect" fails, verify:
> - Token Vault is enabled on your tenant (Step 2)
> - The connection has Token Vault toggled ON (Step 6)
> - MFA is set to Never (Step 5)
> - `OIDC Conformant` is ON for the Web App (Step 4)
> - Callback URLs include both localhost:3000 and localhost:8000 (Step 7)

---

## After Setup: First Login Flow

1. Open `http://localhost:3000`
2. Click **Sign In** → redirected to Auth0 login
3. Create account or log in
4. **Setup Wizard** appears automatically (first-time only)
   - Workspace name auto-filled
   - Auth0 credentials pre-filled from your `.env`
   - Click **Create Workspace**
   - **Save your API Key and HMAC Secret** (shown once, not recoverable)
5. Go to **Demos** → pick any agent → try a scenario

---

## Connecting Services (After Login)

1. Go to **Connections** page
2. Click **Connect** on any service (Stripe, Gmail, Slack, GitHub, etc.)
3. Authorize via OAuth → tokens stored in Auth0 Token Vault
4. The agent can now execute actions on that service without ever seeing credentials

**Important:** This uses Auth0's **Connected Accounts** flow, not the login flow. Tokens must be stored via this flow for Token Vault Token Exchange to work.

---

## Demo Agents

8 AI agents across 5 domains, powered by local LLM (Qwen 2.5 7B via Ollama):

| Domain | Agent | Capabilities |
|--------|-------|-------------|
| Commerce & Finance | Expense & Finance | Refunds, payments, invoices, compensation |
| DevOps | Release Manager | Deploy, rollback, hotfixes |
| Security | Security & Incident Response | Lock repos, revoke tokens, freeze accounts, rotate keys |
| HR & Access | Recruitment & Access | Offer letters, GitHub access, onboarding/offboarding |
| Open Source | Open Source Maintenance | PR merges, releases, bounty payments |
| Research | Research Operations | GPU provisioning, paper submission, datasets |
| Compliance | GDPR Request | Data deletion, transfers, compliance emails |
| Communications | Communications | Slack, email, Discord across all domains |


Each agent has 3 pre-built scenarios (Safe / Risky / Rogue) that demonstrate different ApprovalKit capabilities: auto-approve, step-up authentication, scope creep detection, and more.

The **Live Demo** page provides a split-screen view:
- **Left:** AI agent reasoning + tool calls
- **Right:** ApprovalKit Shield showing approvals, blocks, and pending decisions in real-time

Toggle **Shield ON/OFF** to compare: same agent, same scenario — one protected, one unprotected.

---

## Ollama / LLM Configuration

By default, setup installs **Qwen 2.5 7B** via Ollama (runs locally, no API key needed).

### Using a Different Model

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

Then update `api/services/agent_chat.py`:
```python
"ollama": {"type": "openai", "base_url": "http://ollama:11434/v1", "model": "llama3.1:8b", ...}
```

### Using Groq (Cloud, Free)

If you don't have a GPU or want faster responses:

1. Get a free API key at [console.groq.com](https://console.groq.com/keys)
2. In the app: go to any agent's page → API Key section → select Groq → enter key

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `port already in use` | `docker compose down` then retry, or change ports in docker-compose.yml |
| Login redirect fails | Check Auth0 callback URLs match your hostname |
| "No workspace found" | Complete the Setup Wizard at `/setup` after logging in |
| Chat says "No AI provider" | Run `./setup.sh` again after logging in, or configure manually in app |
| Ollama slow | GPU not detected — install NVIDIA Container Toolkit (see setup.sh output) |
| Token Vault fails | Reconnect the service via Connections page — OAuth tokens may have expired |
| CIBA push not received | Link approver's phone via Guardian app (Approvers page → Link Guardian) |

---

## Commands

```bash
# Start everything
./setup.sh

# Stop
docker compose down

# View logs
docker compose logs -f api
docker compose logs -f worker

# Reset (delete all data)
docker compose down -v && ./setup.sh

# Rebuild after code changes
docker compose up -d --build api worker frontend
```
