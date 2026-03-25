# approvalkit

Human approval middleware for AI agents. Gate any action behind real-time push notifications (Auth0 CIBA + Guardian) and let Token Vault execute it server-side — the agent never holds credentials.

## Install

```bash
# from the repo
pip install ./sdk

# or (once published)
pip install approvalkit
```

## Quick Start

```python
from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url="https://your-approvalkit.example.com",
    api_key="ak_xxxxxxxxxxxx",       # per-agent key from /connect page
    hmac_secret="your-hmac-secret",  # workspace HMAC secret
    user_id="shopping-bot",          # identifies this agent in audit logs
)
```

## Usage Patterns

### 1. Decorator (recommended)

The function body is **never called** — after approval, Token Vault executes the action server-side using stored OAuth credentials.

```python
@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    pass  # body ignored — Token Vault handles execution

result = charge_customer(amount=150, customer="alice@example.com")
# result = {"status": "approved", "final_params": {"amount": 150, ...}}
```

### 2. Inline Gate

```python
result = kit.gate("stripe-prod", "charge", {
    "amount": 150,
    "customer": "alice@example.com",
})
```

### 3. Async Support

```python
@kit.async_requires_approval(connection="github-main", action="deploy")
async def deploy(env: str, branch: str):
    pass

result = await deploy(env="production", branch="main")

# or inline
result = await kit.async_gate("github-main", "deploy", {
    "env": "production",
    "branch": "main",
})
```

### 4. Custom Params Builder

```python
@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda amount, cust: {"amount_usd": amount, "customer": cust},
)
def charge(amount: int, cust: str):
    pass
```

## Error Handling

```python
from approvalkit import ApprovalDenied

try:
    result = kit.gate("stripe-prod", "charge", {"amount": 5000})
except ApprovalDenied as e:
    print(f"Action was {e.status}")  # "rejected", "timeout", or "blocked"
    print(f"Job ID: {e.job_id}")
```

| Status | Meaning |
|--------|---------|
| `approved` | Approved by human, Token Vault executed the action |
| `pre_approved` | Matched a pre-approval rule, auto-executed |
| `rejected` | Approver denied the request |
| `timeout` | No response within the rule's timeout window |
| `blocked` | Policy violation (cooldown, blackout, scope creep) |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `base_url` | `http://localhost:8000` | ApprovalKit API URL |
| `api_key` | `""` | Per-agent API key (`ak_*` format) |
| `hmac_secret` | `""` | Workspace HMAC secret for request signing |
| `user_id` | `"agent"` | Agent identifier for audit logs |
| `poll_interval` | `3` | Seconds between status polls |
| `timeout` | `300` | Max seconds to wait for approval |

## How It Works

```
Agent calls kit.gate()
    → SDK signs request with HMAC-SHA256
    → POST /api/v1/request
    → Rule engine evaluates conditions
    → CIBA push notification sent to approver's phone (Auth0 Guardian)
    → Approver taps Approve / Reject
    → If approved: Token Vault exchanges refresh_token for access_token (RFC 8693)
    → Token Vault executes the action (Stripe charge, GitHub deploy, etc.)
    → SDK receives result
```

The agent **never sees** the OAuth token. Credentials stay in Auth0 Token Vault.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Invalid signature` | Wrong HMAC secret or clock skew > 5min | Check `hmac_secret`, sync system clock |
| `403 No matching rule` | No active rule for this connection/action | Create a rule in the dashboard |
| `ApprovalDenied("blocked")` | Cooldown, blackout, or scope creep triggered | Check rule conditions in dashboard |
| `ApprovalDenied("timeout")` | Approver didn't respond in time | Increase rule timeout or check Guardian enrollment |
| `Connection refused` | ApprovalKit API not running | Check `base_url` and API health (`/health`) |

## Full Example

```python
from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url="http://localhost:8000",
    api_key="ak_abc123...",
    hmac_secret="your-workspace-hmac-secret",
    user_id="e-commerce-bot",
)

def process_order(order):
    # Step 1: Charge customer (requires approval if amount > $100)
    try:
        result = kit.gate("stripe-prod", "charge", {
            "amount": order["total"],
            "customer": order["email"],
            "description": f"Order #{order['id']}",
        })
        print(f"Charged: {result['final_params']}")
    except ApprovalDenied as e:
        print(f"Payment {e.status} — order cancelled")
        return

    # Step 2: Deploy updated inventory (auto-approved for small changes)
    try:
        kit.gate("github-main", "deploy", {
            "ref": "main",
            "environment": "production",
        })
    except ApprovalDenied:
        print("Deploy blocked — manual intervention needed")
```
