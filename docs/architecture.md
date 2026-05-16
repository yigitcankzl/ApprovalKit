# Architecture

ApprovalKit sits between an AI agent and the systems it acts on.
Every call goes through five stages: **request → rule evaluation →
approval → execution → audit**.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   AI Agent   │───▶│  ApprovalKit │───▶│   Approval   │───▶│    Human     │
│  (any LLM)   │    │    API +     │    │   Channel    │    │  (phone /    │
│              │    │   Worker     │    │  (CIBA/local)│    │   web /…)    │
└──────────────┘    └──────┬───────┘    └──────────────┘    └──────┬───────┘
                           │                                       │
                    Rule engine                            Approve / deny
                    Risk + step-up                                  │
                           │            ┌──────────────┐           │
                           └───────────▶│  Credential  │◀──────────┘
                                        │    Store     │
                                        │ (Auth0 TV /  │
                                        │   local)     │
                                        └──────┬───────┘
                                               │
                                        ┌──────┴───────┐
                                        │  Stripe /    │
                                        │  GitHub /    │
                                        │  Slack / …   │
                                        └──────────────┘
```

## Components

### API (FastAPI)

Stateless request handler. Validates the incoming payload, signs/
verifies HMAC, persists an `ApprovalJob`, and hands off to the worker
for the long-running approval flow. Exposes SSE for the dashboard.

### Worker (Celery)

Drives the approval lifecycle:

1. Evaluates the matching rule(s) and computes a risk score.
2. Determines the approval model (`any_one`, `all_of_n`, …) and the
   list of approvers — escalating via step-up rules when needed.
3. Asks the active **ApprovalChannel** to dispatch the request and
   waits for the response.
4. On approval, asks the active **CredentialStore** for a short-lived
   access token and calls the downstream service through a built-in
   handler (Stripe, GitHub, …) or a generic webhook.
5. Writes a hash-chained audit entry.

### Provider layer

The worker doesn't know whether it's talking to Auth0 or to the local
backends — it sees `ApprovalChannel` and `CredentialStore` protocol
objects. See [`providers.md`](providers.md).

### Database (PostgreSQL)

Stores workspaces, rules, approvers, agents, connections, approval
jobs, and audit logs. Credentials are Fernet-encrypted at rest.

### Redis

Drives Celery, the SSE event bus, the circuit breakers, rate limits,
and the local approval channel's pending-request store.

## Request lifecycle

```
POST /api/v1/request
    │
    ▼
[validate HMAC + payload]
    │
    ▼
[match rules, compute risk]
    │
    ▼
[create ApprovalJob, return job_id]   ← API returns here
    │
    ▼   (Celery picks up the job)
[dispatch to ApprovalChannel.initiate()]
    │
    ▼
[ApprovalChannel.poll() until terminal]
    │
    ▼
[CredentialStore.get_access_token(...)]
    │
    ▼
[handler.execute(action, params, token)]
    │
    ▼
[audit + SSE event]
```

## Where to look in the code

| Concern              | Location                                |
|----------------------|-----------------------------------------|
| HTTP entry points    | `api/routes/*`                          |
| Rule engine          | `api/services/rule_engine.py`           |
| Worker tasks         | `api/worker/tasks.py`                   |
| Approval channels    | `api/providers/{auth0,local}/approval.py` |
| Credential stores    | `api/providers/{auth0,local}/credentials.py` |
| Service handlers     | `api/services/token_vault.py` (`execute_action`) |
| Audit / hash chain   | `api/services/...` + `api/models/approval_job.py` |
