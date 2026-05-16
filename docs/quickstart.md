# Quickstart

This page walks through the fastest possible path to a working
ApprovalKit setup. Two flavours are supported:

* **Local mode** — no Auth0, no external accounts. Approvals happen
  through a small HTTP endpoint backed by Redis. Best for local dev,
  evaluations, and CI.
* **Auth0 mode** — the production-grade setup using Auth0 CIBA push
  notifications and Token Vault. See [`SETUP.md`](https://github.com/yigitcankzl/ApprovalKit/blob/main/SETUP.md) for
  the full Auth0 walkthrough.

## 1. Clone and configure

```bash
git clone https://github.com/yigitcankzl/ApprovalKit.git
cd ApprovalKit
cp .env.example .env
```

For local mode, set:

```env
APPROVAL_PROVIDER=local
ENVIRONMENT=development
HMAC_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

For Auth0 mode, populate the `AUTH0_*` variables from your tenant and
keep `APPROVAL_PROVIDER=auth0`.

## 2. Boot the stack

Local mode (no Ollama, no Auth0):

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up
```

Auth0 mode (full stack):

```bash
./setup.sh
```

The API lives on `http://localhost:8000` and the dashboard on
`http://localhost:3000`.

## 3. Install the SDK

```bash
pip install ./sdk
```

## 4. Gate a function

```python
from approvalkit import ApprovalKit

kit = ApprovalKit(
    base_url="http://localhost:8000",
    api_key="<from /connect page>",
    hmac_secret="<HMAC_SECRET from .env>",
    user_id="my-agent",
)

@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    # The body never runs. ApprovalKit asks a human; if approved, the
    # credential store executes the action server-side.
    pass

result = charge_customer(amount=120, customer="alice@example.com")
print(result)  # {"status": "approved", ...} or raises ApprovalDenied
```

## 5. Approve a request (local mode)

The API logs an `auth_req_id`-style handle when the request lands.
Approve it with curl:

```bash
curl -X POST http://localhost:8000/local-approvals/<handle>/approve
```

Or reject:

```bash
curl -X POST http://localhost:8000/local-approvals/<handle>/reject
```

For unattended runs (CI), set
`LOCAL_APPROVAL_AUTO_APPROVE=true` so every request is approved
automatically. **Never enable this in production.**

## Next steps

* Read [`providers.md`](providers.md) to understand or swap the
  approval channel and credential store.
* Browse [`examples/`](https://github.com/yigitcankzl/ApprovalKit/tree/main/examples) for reference agents (e-commerce,
  HR, devops, finance) that cover real approval scenarios.
* See [`approval-models.md`](approval-models.md) for the six built-in
  approval models.
