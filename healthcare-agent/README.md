# Healthcare AI Agent

A comprehensive, HIPAA-compliant healthcare management system powered by [ApprovalKit](../README.md) — demonstrating every approval feature in realistic hospital scenarios.

## What It Does

This agent manages a complete hospital workflow:

- **Patient Registration & Onboarding** — auto-notify doctors, Slack announcements, insurance verification, appointment scheduling
- **Prescription Management** — routine medications (doctor approval), controlled substances (doctor + pharmacist sequential), dose changes (doctor + pharmacist + CMO all-of-n)
- **HIPAA Data Sharing** — external referrals, insurance data requests with partial approval (scope narrowing), research exports with amount anomaly detection
- **Billing & Insurance** — auto-approve under $500, step-up escalation ($10k, $25k tiers), insurance appeals
- **Emergency Situations** — 2-minute timeout data access, security breach auto-freeze
- **Staff Management** — doctor vacation delegation, access level step-up

## ApprovalKit Features Used

| Feature | Healthcare Use Case |
|---------|-------------------|
| Token Vault | Gmail, Slack, Calendar, Drive — agent never holds credentials |
| CIBA Guardian | Push notification approvals to doctor/staff phones |
| any_one | Emergency data access — first available doctor |
| specific | Routine prescriptions — prescribing doctor |
| all_of_n | Dose changes — doctor + pharmacist + CMO |
| sequential | Controlled substances — doctor then pharmacist |
| step-up | Billing escalation: $500 → $10k → $25k |
| partial_approval | Insurance data — approver narrows scope (full → summary) |
| delegation | Doctor vacation handoff |
| blackout_window | No billing operations 22:00-06:00 |
| scope_creep | First dose change auto-flagged |
| amount_anomaly | Research export: 100+ patients flagged |
| audit_trail | HIPAA compliance — immutable, PII-masked |
| timeout_escalation | Emergency: 2-min timeout → escalate to CMO |

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 16 (or Docker)
- ApprovalKit running at `localhost:8000`

### Option 1: Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your ApprovalKit credentials

docker compose up -d --build
```

### Option 2: Local development

```bash
# Start PostgreSQL
docker run -d --name healthcare-db \
  -e POSTGRES_DB=healthcare_agent \
  -e POSTGRES_USER=healthcare \
  -e POSTGRES_PASSWORD=healthcare \
  -p 5433:5432 postgres:16-alpine

# Install dependencies
pip install -r backend/requirements.txt

# Start backend
make dev

# Seed database
make seed

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Provision ApprovalKit Rules

```bash
export APPROVALKIT_URL=http://localhost:8000
export APPROVALKIT_API_KEY=ak_your_key
export APPROVALKIT_HMAC_SECRET=your_secret

make provision
```

This creates 9 connections, 10 approvers, and 15 rules in ApprovalKit.

## Architecture

```
Frontend (Next.js :3003) → Backend (FastAPI :3002) → ApprovalKit (:8000)
                                    ↓
                              PostgreSQL (:5433)
```

**Interfaces:**
- Web Dashboard: `http://localhost:3003`
- API: `http://localhost:3002`
- CLI: `python -m agent.healthcare_agent --interactive`
- MCP Server: `python -m mcp_server.server` (Claude Desktop)
- A2A: `POST http://localhost:3002/a2a`

## Demo Scenarios (14)

Run from the web UI at `/scenarios` or via CLI:

```bash
python -m agent.healthcare_agent --scenario patient-onboarding
python -m agent.healthcare_agent --scenario controlled-substance
python -m agent.healthcare_agent --scenario emergency-access
python -m agent.healthcare_agent --list-scenarios
```

| # | Scenario | Approval Model | Key Feature |
|---|----------|---------------|-------------|
| 1 | Patient Onboarding | auto (Token Vault) | Gmail + Slack + Calendar |
| 2 | Routine Prescription | specific | Doctor approval |
| 3 | Controlled Substance | sequential | Doctor → Pharmacist |
| 4 | Dose Change | all_of_n + scope_creep | Doctor + Pharmacist + CMO |
| 5 | External Referral | specific | Drive share + Gmail |
| 6 | Insurance Data | all_of_n + partial_approval | Scope narrowing |
| 7 | Research Export | sequential + amount_anomaly | 150 patients flagged |
| 8 | Small Billing | auto (no rule) | <$500 auto-approve |
| 9 | Large Billing | step-up | $500 → $10k → $25k tiers |
| 10 | Insurance Appeal | all_of_n | Doctor + Finance |
| 11 | Emergency Access | any_one | 2-min timeout, no blackout |
| 12 | Security Breach | all_of_n + auto_freeze | Security + CMO |
| 13 | Doctor Delegation | delegation | Vacation handoff |
| 14 | Staff Access | step-up + all_of_n | IT → IT+CMO → IT+Pharmacy+CMO |

## Seed Data

The `/api/seed` endpoint generates:
- 55 realistic patients with medical histories
- 24 doctors across 15 specialties
- 16 staff (pharmacists, nurses, IT, finance, security, ethics, admin)
- 5 insurance providers (BlueCross, Aetna, UHC, Cigna, Medicare)
- 25 prescriptions (routine + controlled)
- 30 billing records ($35 to $35,000)
- 40 appointments
- 60 shift schedule entries

## MCP Integration

Add to Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "healthcare-agent": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/healthcare-agent",
      "env": {
        "HEALTHCARE_API_URL": "http://localhost:3002"
      }
    }
  }
}
```

Available MCP tools: `register_patient`, `prescribe_medication`, `request_dose_change`, `process_billing`, `create_referral`, `emergency_access`, `report_breach`, `lookup_patient`, `list_patients`, `check_approval_status`, `get_dashboard_stats`

## A2A Integration

Agent card: `GET http://localhost:3002/.well-known/agent.json`

```python
import httpx

response = httpx.post("http://localhost:3002/a2a", json={
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "id": "1",
    "params": {
        "message": {
            "parts": [{
                "type": "application/json",
                "data": {"skill": "emergency-access", "patient_id": "...", "reason": "..."},
                "metadata": {"skill": "emergency-access"}
            }]
        }
    }
})
```

## Project Structure

```
healthcare-agent/
├── backend/                  # FastAPI backend
│   ├── models/              # 13 SQLAlchemy models
│   ├── schemas/             # Pydantic validation
│   ├── routes/              # 8 API routers
│   ├── services/            # Business logic + ApprovalKit gateway
│   └── seed/                # Data generation (55+ patients)
├── frontend/                # Next.js 14 dashboard
│   └── src/app/             # 8 pages + components
├── agent/                   # CLI agent
├── mcp_server/              # MCP tools for Claude Desktop
├── a2a/                     # A2A protocol server
├── setup/                   # ApprovalKit rule provisioner
├── docs/                    # Architecture, flows, API reference
├── docker-compose.yml       # Full stack orchestration
└── Makefile                 # Dev commands
```

## Documentation

- [Architecture](docs/architecture.md) — System overview, data flow, technology stack
- [Approval Flows](docs/approval-flows.md) — All 17 approval scenarios with detailed flow diagrams
- [API Reference](docs/api-reference.md) — Complete endpoint documentation
