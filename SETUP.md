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

If you want to use your own Auth0 account instead of the demo tenant, follow these steps:

### Step 1: Create Auth0 Applications

Go to [Auth0 Dashboard](https://manage.auth0.com) and create two applications:

#### A. Backend M2M Application

1. **Applications → Create Application → Machine to Machine**
2. Name: `ApprovalKit Backend`
3. Authorize it for the **Auth0 Management API** with these scopes:
   - `read:users`
   - `read:connections`
   - `read:users_app_metadata`
4. Copy the **Client ID** and **Client Secret**

#### B. Frontend Web Application

1. **Applications → Create Application → Regular Web Application**
2. Name: `ApprovalKit Web`
3. Settings:
   - **Allowed Callback URLs:** `http://localhost:3000/api/auth/callback`
   - **Allowed Logout URLs:** `http://localhost:3000`
   - **Allowed Web Origins:** `http://localhost:3000`
4. **Advanced Settings → Grant Types:** Enable:
   - `Authorization Code`
   - `Refresh Token`
   - `Client Credentials`
5. Copy the **Client ID** and **Client Secret**

### Step 2: Enable Token Vault

1. Go to **Auth0 Dashboard → Auth0 for AI Agents** (or Settings → Token Vault)
2. Enable Token Vault on your tenant
3. On the Web Application settings, enable the **Token Vault grant type**
4. Set **MFA Policy** to **Never** (Token Exchange doesn't support MFA)

### Step 3: Configure Social Connections (Optional)

For each service you want agents to control, create an OAuth connection:

#### Stripe
1. [Stripe Dashboard → Developers → API Keys](https://dashboard.stripe.com/apikeys)
2. Auth0: **Authentication → Social → Stripe** → enter Client ID + Secret
3. Enable **Token Vault** toggle on the connection

#### Google (Gmail, Calendar, Drive)
1. [Google Cloud Console → OAuth Client](https://console.cloud.google.com/apis/credentials)
2. Authorized redirect URI: `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Scopes: `email profile https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar.events`
4. Auth0: **Authentication → Social → Google** → enter Client ID + Secret
5. Add `access_type: offline` in upstream params (for refresh tokens)
6. Enable **Token Vault** toggle

#### GitHub
1. [GitHub → Developer Settings → OAuth Apps](https://github.com/settings/developers)
2. Callback URL: `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Auth0: **Authentication → Social → GitHub** → enter Client ID + Secret
4. Enable **Token Vault** toggle

#### Slack
1. [Slack API → Create App](https://api.slack.com/apps)
2. Redirect URL: `https://YOUR_AUTH0_DOMAIN/login/callback`
3. Scopes: `chat:write`, `channels:read`
4. Auth0: **Authentication → Social → Custom Social** → enter OAuth details
5. Enable **Token Vault** toggle

#### Other Services

Auth0 Token Vault supports 30+ providers. Any OAuth2 provider can be added as a Custom Social Connection. See [Auth0 Token Vault Integrations](https://auth0.com/ai/docs/intro/integrations).

### Step 4: Configure FGA (Optional)

Fine-Grained Authorization adds role-based access control:

1. Go to [FGA Dashboard](https://dashboard.fga.dev)
2. Create a store
3. Create an authorization model
4. Create M2M credentials
5. Copy Store ID, Model ID, Client ID, Client Secret

### Step 5: Configure CIBA / Guardian (Optional)

For push notification approvals to mobile phones:

1. Auth0 Dashboard → **Security → Multi-factor Auth → Guardian**
2. Enable push notifications
3. Download Auth0 Guardian app on approver's phone
4. Link approver's Auth0 account to Guardian (done via ApprovalKit dashboard)

### Step 6: Update Environment Files

Edit `.env`:
```bash
# Auth0
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your-m2m-client-id
AUTH0_CLIENT_SECRET=your-m2m-client-secret
AUTH0_WEB_CLIENT_ID=your-web-client-id
AUTH0_WEB_CLIENT_SECRET=your-web-client-secret
AUTH0_AUDIENCE=https://your-tenant.us.auth0.com/me/
AUTH0_MGMT_API_AUDIENCE=https://your-tenant.us.auth0.com/api/v2/

# FGA (optional)
FGA_API_URL=https://api.us1.fga.dev
FGA_STORE_ID=your-store-id
FGA_MODEL_ID=your-model-id
FGA_CLIENT_ID=your-fga-client-id
FGA_CLIENT_SECRET=your-fga-client-secret
```

Edit `frontend/.env.local`:
```bash
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your-web-client-id
AUTH0_CLIENT_SECRET=your-web-client-secret
AUTH0_BASE_URL=http://localhost:3000
AUTH0_SECRET=generate-a-random-32-byte-hex-string
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Step 7: Start

```bash
./setup.sh
```

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

14 AI agents across 6 domains, powered by local LLM (Qwen 2.5 7B via Ollama):

| Domain | Agents |
|--------|--------|
| Commerce & Finance | Expense, Finance |
| DevOps & Software | Release Manager, Open Source |
| Human Resources | Recruitment, Access Provisioning |
| Customer Service | Account Takeover |
| Healthcare | Patient Data, Prescription Refill |
| Legal & Compliance | GDPR, API Key Rotation, Security Incident |

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

## Healthcare Agent (Companion Demo)

A separate HIPAA-compliant healthcare demo with its own frontend:

```bash
cd healthcare-agent
docker compose up -d
# Frontend: http://localhost:3003
# API: http://localhost:3002
```

14 healthcare scenarios: routine prescriptions, controlled substances (sequential approval), HIPAA data sharing, emergency access (2-minute timeout), billing step-up, and more.

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
