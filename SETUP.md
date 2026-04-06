# ApprovalKit — Setup Guide

## Quick Start

```bash
git clone https://github.com/yigitcankzl/ApprovalKit.git
cd ApprovalKit
cp .env.example .env
# Edit .env with your Auth0 credentials (see Step 10 below)
chmod +x setup.sh
./setup.sh
```

After editing `.env` with your Auth0 credentials, `setup.sh` starts all services. Open `http://localhost:3000`, log in, and start using the demo agents.

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

## Quick Path for Judges (5-Minute Setup)

If you want to test with your own Auth0 tenant, here's the fast path:

1. **Auth0 Dashboard** — Create 2 apps (M2M + Web), enable Token Vault
2. **Edit `.env`** — paste your Auth0 credentials (setup.sh auto-generates `frontend/.env.local`)
3. **Run `./setup.sh`** — starts all services
4. **Login + Setup Wizard** — enter credentials, click **Test Connection** to verify
5. **Connect a service** — go to Connections, click Connect on Stripe/Google/GitHub

The Setup Wizard has a **Test Connection** button that checks:
- Domain reachability
- M2M credential validity
- Management API scopes
- Token Vault connection count

If any check fails, the wizard shows exactly what to fix. You don't need to guess.

> **Minimum viable setup**: Auth0 free tier + 1 M2M app + 1 Web app + Token Vault enabled. No FGA, Guardian, or social connections required for the basic demo.

---

## Using Your Own Auth0 Tenant (Detailed)

If you want to use your own Auth0 account instead of the demo tenant, follow these steps carefully. Every step is critical — missing one will cause silent failures.

### Step 1: Create Auth0 Tenant

1. Sign up at [auth0.com](https://auth0.com) (free tier works)
2. Create a new tenant (e.g., `approvalkit-dev`)
3. Note your **tenant domain**: `your-tenant.us.auth0.com`

### Step 2: Enable Token Vault

This is the most important step — without it, Token Exchange won't work.

Token Vault is enabled in **two places**:

1. **Per-application:** Go to **Applications → Your App → Settings → Advanced Settings → Grant Types** → check **"Token Vault"**
2. **Per-connection:** Go to **Authentication → Social Connections → [Connection] → Advanced** → under **Purpose**, enable **"Connected Accounts for Token Vault"**

Both must be enabled for Token Exchange to work. When Token Vault is enabled on a connection, access/refresh tokens are managed by Token Vault.

> **Note:** On some free-tier tenants, Token Vault may require manual enablement. If you don't see the Token Vault grant type in your app settings, submit a support ticket at [Auth0 Support](https://support.auth0.com) or check the [community thread](https://community.auth0.com/t/request-to-enable-token-vault-early-access-for-hackathon-tenant/198372).

> **Critical:** Token Exchange (RFC 8693) can only access tokens stored in Token Vault. Make sure Token Vault is toggled ON for each social connection you want agents to use (Step 6).

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
   - **Allowed Callback URLs** (add BOTH lines):
     ```
     http://localhost:3000/api/auth/callback
     http://localhost:8000/api/v1/connections/oauth/callback
     ```
   - **Allowed Logout URLs:**
     ```
     http://localhost:3000
     ```
   - **Allowed Web Origins** (add BOTH lines):
     ```
     http://localhost:3000
     http://localhost:8000
     ```
4. **Settings → Advanced Settings → Grant Types**, enable ALL of these:
   - `Authorization Code`
   - `Refresh Token`
   - `Client Credentials`
   - `Token Vault` (labeled "Token Vault" in the dashboard — this is the Token Exchange grant)
5. **Settings → Advanced Settings → OAuth:**
   - `OIDC Conformant`: **ON** (required for Token Vault)
   - `Trust Token Endpoint IP Header`: **OFF**
6. Copy **Client ID** and **Client Secret**

### Step 5: Set MFA Policy

Auth0 docs explicitly state: MFA policy must be set to **Never** for Token Vault to retrieve tokens. If MFA is set to "Always", Token Exchange will fail with `mfa_required` errors.

1. **Security → Multi-factor Authentication**
2. Set **Policy** to **Never**

> This applies to the Token Exchange flow specifically. CIBA (push notification approvals) uses a separate MFA mechanism via Guardian and is not affected by this setting.

### Step 6: Configure Social Connections

For each service you want agents to control:

#### A. Stripe

1. [Stripe Dashboard → Developers → OAuth](https://dashboard.stripe.com/settings/connect) → Create OAuth app
2. Set redirect URI: `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Auth0: **Authentication → Social → Create Connection → Stripe**
4. Enter Stripe Client ID + Secret
5. **Important:** Under **Purpose**, enable **"Connected Accounts for Token Vault"** for this connection
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
7. Under **Purpose**, enable **"Connected Accounts for Token Vault"**

#### C. GitHub

1. [GitHub → Settings → Developer Settings → OAuth Apps](https://github.com/settings/developers) → New OAuth App
2. Authorization callback URL: `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Auth0: **Authentication → Social → GitHub** → enter Client ID + Secret
4. Under **Permissions**, add scope: `repo,workflow`
5. Under **Purpose**, enable **"Connected Accounts for Token Vault"**

> Note: GitHub uses long-lived access tokens (no refresh token). If the token expires, the user must reconnect via the Connections page.

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
6. Under **Purpose**, enable **"Connected Accounts for Token Vault"**

#### E. Other Services (Discord, PayPal, Figma, etc.)

Auth0 Token Vault supports 26+ OAuth providers. For any service:

1. Create OAuth app on the service's developer portal
2. Set redirect URI to `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Auth0: **Authentication → Social → Create Connection**
4. Enter Client ID + Secret
5. Under **Purpose**, enable **"Connected Accounts for Token Vault"**
6. Ensure the connection requests `offline_access` or equivalent for refresh tokens

See [Auth0 Token Vault Integrations](https://auth0.com/ai/docs/intro/integrations) for the full list.

### Step 7: Verify Callback URLs

If you followed Step 4 correctly, your callback URLs are already set. Double-check that your Web App has these URLs whitelisted:

- **Allowed Callback URLs:** `http://localhost:3000/api/auth/callback` (login) and `http://localhost:8000/api/v1/connections/oauth/callback` (service connections)
- **Allowed Web Origins:** `http://localhost:3000` and `http://localhost:8000`

> The service connection flow redirects through Auth0 OAuth to link external services (Stripe, Google, etc.). The refresh token is stored and later used for Token Exchange.

### Step 8: Configure FGA (Optional)

Fine-Grained Authorization adds role-based access control (admin/approver/viewer). Skip this for basic demos.

1. Go to [FGA Dashboard](https://dashboard.fga.dev)
2. Create a new store → copy **Store ID**
3. Create authorization model (use `fga/model.fga` from this repo) → copy **Model ID**
4. **Settings → API Credentials** → Create M2M credentials → copy **Client ID** + **Client Secret**
5. If FGA is not configured, all authorization checks pass (allow-all) — the app works but without RBAC

### Step 9: Configure CIBA / Guardian (Optional)

For push notification approvals to mobile phones (instead of web dashboard):

> **Note:** CIBA may require an Essentials plan or the Auth0 for AI Agents add-on. On free-tier tenants, CIBA might not be available. Without CIBA, approvals happen via the web dashboard — all other features work normally.

1. **Applications → Your Web App → Settings → Advanced → Grant Types** → enable **"Client-Initiated Backchannel Authentication (CIBA)"**
2. **Applications → Your Web App → Settings** → scroll to **CIBA section** → configure notification channels
3. Auth0 Dashboard → **Security → Multi-factor Auth → Push via Auth0 Guardian** → enable
4. Each approver needs to:
   - Download **Auth0 Guardian** app ([iOS](https://apps.apple.com/app/auth0-guardian/id1093447833) / [Android](https://play.google.com/store/apps/details?id=com.auth0.guardian))
   - Enroll in MFA via the Guardian app
   - Link their Auth0 account via the ApprovalKit Approvers page → "Link Guardian"
5. CIBA push notifications are sent when an approval is pending — approver taps Approve/Deny on their phone

> Without Guardian, approvals happen via the web dashboard (ApprovalKit Approve/Reject buttons). Guardian adds mobile push notifications as an additional channel.

### Step 10: Update Environment Files

You only need to edit **one file**: `.env`. The setup script auto-generates `frontend/.env.local` from it.

Edit `.env`:
```bash
# Auth0 (REQUIRED) — create 2 apps in Auth0 Dashboard:
# 1. M2M app (for backend token exchange)    → AUTH0_CLIENT_ID / AUTH0_CLIENT_SECRET
# 2. Web app (for frontend user login)       → AUTH0_WEB_CLIENT_ID / AUTH0_WEB_CLIENT_SECRET

AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your-m2m-client-id
AUTH0_CLIENT_SECRET=your-m2m-client-secret
AUTH0_WEB_CLIENT_ID=your-web-client-id
AUTH0_WEB_CLIENT_SECRET=your-web-client-secret
AUTH0_AUDIENCE=https://your-tenant.us.auth0.com/me/
AUTH0_MGMT_API_AUDIENCE=https://your-tenant.us.auth0.com/api/v2/
```

> **Note:** `HMAC_SECRET` and `AUTH0_SECRET` (frontend) are auto-generated by `./setup.sh`. You don't need to generate them manually.

> **Note:** `frontend/.env.local` is auto-generated from `.env` by `./setup.sh`. It uses `AUTH0_WEB_CLIENT_ID` and `AUTH0_WEB_CLIENT_SECRET` for frontend login. You don't need to edit it separately.

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

10 specialized AI agents across 6 domains, powered by local LLM (auto-detected via Ollama):

| Domain | Agent | Capabilities |
|--------|-------|-------------|
| Commerce & Finance | Expense & Finance | Refunds, payments, invoices, compensation |
| DevOps | Release Manager | Deploy, rollback, hotfixes |
| Security | Security Incident Response | Lock repos, revoke tokens, freeze accounts |
| HR | Recruitment | Offer letters, interview invites, terminations |
| Compliance | GDPR Request | Data deletion, transfers, compliance emails |
| Open Source | Open Source Maintenance | PR merges, releases, bounty payments |
| Research | Research Operations | GPU provisioning, paper submission, datasets |
| Communications | Communications | Slack, email, Discord across all domains |
| Infrastructure | Key Rotation | API key rotation, credential management |
| IAM | Access Provisioning | Grant/revoke access, onboarding |


Each agent has 3 pre-built scenarios (Safe / Risky / Rogue) that demonstrate different ApprovalKit capabilities: auto-approve, step-up authentication, scope creep detection, and more.

The **AI Orchestrator** (`/demos/live?chain=orchestrator`) is the recommended entry point:
- Describe any business situation in plain text
- AI plans a multi-agent workflow with per-step least privilege
- 7 sub-agents analyze risk, cost, compliance, rollback before execution
- 24+ preset scenarios including 4 rogue agent tests

The **Live Demo** page provides a split-screen view:
- **Left:** AI agent reasoning + tool calls + chain progress bar
- **Right:** ApprovalKit Shield showing approvals, blocks, and pending decisions in real-time
- **Stop Chain** button to halt execution mid-workflow

Toggle **Shield ON/OFF** to compare: same agent, same scenario — one protected, one unprotected.

---

## Ollama / LLM Configuration

By default, setup installs **Qwen 2.5 7B** via Ollama (runs locally, no API key needed).

### Using a Different Model

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

The API auto-detects the first available Ollama model at startup — no config change needed. Just pull and restart:

```bash
docker compose restart api
```

### Using Groq (Cloud, Free)

If you don't have a GPU or want faster responses:

1. Get a free API key at [console.groq.com](https://console.groq.com/keys)
2. In the app: go to **Settings** page → AI API Key section → select Groq → enter key

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Token Vault grant type not visible | Submit support ticket at [Auth0 Support](https://support.auth0.com) to enable Token Vault on your tenant |
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
