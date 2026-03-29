# Healthcare AI Agent — Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     Healthcare AI Agent                           │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Next.js 14  │  │  FastAPI      │  │  PostgreSQL   │           │
│  │  Frontend    │─→│  Backend      │─→│  Database     │           │
│  │  :3003       │  │  :3002        │  │  :5433        │           │
│  └─────────────┘  └──────┬───────┘  └──────────────┘           │
│                          │                                        │
│  ┌─────────────┐         │         ┌──────────────┐             │
│  │  MCP Server  │         │         │  A2A Server   │             │
│  │  (Claude)    │─────────┤─────────│  (Agents)     │             │
│  └─────────────┘         │         └──────────────┘             │
│                          │                                        │
│  ┌─────────────┐         │                                        │
│  │  CLI Agent   │─────────┘                                        │
│  └─────────────┘                                                  │
└──────────────────────────────────────────────────────────────────┘
                           │
                    ApprovalKit SDK
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                       ApprovalKit                                 │
│                                                                   │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐     │
│  │ Rule    │  │ CIBA    │  │ Token    │  │ Audit        │     │
│  │ Engine  │  │ Guardian│  │ Vault    │  │ Trail        │     │
│  └────┬────┘  └────┬────┘  └─────┬────┘  └──────────────┘     │
│       │            │              │                               │
│       ▼            ▼              ▼                               │
│  Conditions    Push Notify   Service Execution                    │
│  Step-up       Approve/Deny  Gmail, Slack, Calendar, Drive       │
│  Blackout      Delegation    Stripe, GitHub, etc.                │
│  Cooldown      Timeout       Generic Webhook                      │
│  Scope Creep   Escalation                                         │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Approval Request Flow

```
Agent → ApprovalKit SDK → POST /api/v1/request
                            │
                    Rule Engine evaluates:
                    ├── Condition matching
                    ├── Scope creep detection
                    ├── Amount anomaly check
                    ├── Budget enforcement
                    ├── Blackout window check
                    ├── Cooldown check
                    ├── Pre-approval check
                    └── Step-up evaluation
                            │
                    Celery Worker:
                    ├── CIBA push → Guardian app
                    ├── Approval model execution
                    │   ├── any_one: first approver wins
                    │   ├── specific: designated approver
                    │   ├── all_of_n: every approver
                    │   ├── sequential: ordered chain
                    │   └── k_of_n: quorum
                    └── Delegation resolution
                            │
                    On Approval:
                    ├── Token Vault → fresh token
                    ├── Service execution
                    ├── Audit log entry
                    └── SDK returns result
```

### 2. Healthcare Agent Internal Flow

```
Frontend / CLI / MCP / A2A
          │
    FastAPI Routes
          │
    Business Logic Services
    ├── PatientService      → approval_gateway.py
    ├── PrescriptionService → approval_gateway.py
    ├── BillingService      → approval_gateway.py
    ├── ReferralService     → approval_gateway.py
    ├── EmergencyService    → approval_gateway.py
    └── StaffService        → approval_gateway.py
          │
    ApprovalGateway (centralized wrapper)
          │
    ApprovalKit SDK (kit.gate())
          │
    NotificationService
    ├── Gmail (doctor notification, pharmacy)
    ├── Slack (#intake, #emergency, #billing)
    ├── Calendar (appointments)
    └── Drive (record sharing)
```

## Database Schema

The Healthcare Agent maintains its own PostgreSQL database, separate from ApprovalKit's.
All approval state (jobs, audit logs) lives in ApprovalKit.
The agent's DB holds domain data only.

### Tables (13)

| Table | Description | Key Relations |
|-------|-------------|---------------|
| patients | Patient demographics, conditions, allergies | → doctors, insurance_providers |
| doctors | Physicians with NPI, specialty, delegation | → doctors (self-referential delegate) |
| staff | Non-physician staff (nurses, pharmacists, IT) | — |
| prescriptions | Medication orders with approval tracking | → patients, doctors |
| dose_changes | Dosage modification requests | → prescriptions, patients, doctors |
| appointments | Scheduled visits | → patients, doctors |
| billing_records | Invoices with step-up tracking | → patients |
| insurance_providers | Insurance companies | — |
| insurance_requests | Data sharing requests to insurance | → patients, insurance_providers |
| referrals | External clinic and research data sharing | → patients, doctors |
| emergency_events | Critical situations | → patients |
| shift_schedule | Doctor shifts with delegation | → doctors |
| access_requests | Staff access level changes | → staff |
| activity_log | Internal event stream | — |

## Technology Stack

### Backend
- **Python 3.12** + **FastAPI** (async web framework)
- **SQLAlchemy 2.0** (async ORM with PostgreSQL)
- **Pydantic v2** (request/response validation)
- **httpx** (async HTTP client)
- **ApprovalKit SDK** (approval gateway)

### Frontend
- **Next.js 14** (React SSR)
- **TypeScript** (type safety)
- **Tailwind CSS 3** (styling)

### Infrastructure
- **PostgreSQL 16** (database)
- **Docker Compose** (orchestration)

### Integration
- **MCP** (Model Context Protocol for Claude Desktop)
- **A2A** (Agent-to-Agent for inter-agent communication)
- **ApprovalKit** (approval middleware)
