# Python SDK reference

## Install

```bash
# from the repo (pip publish coming soon)
pip install ./sdk
```

## Client

```python
from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url="http://localhost:8000",   # ApprovalKit API URL
    api_key="ak_xxxxxxxxxxxx",          # per-agent key from /connect
    hmac_secret="<HMAC_SECRET>",        # workspace HMAC secret
    user_id="my-agent",                 # appears in audit logs
)
```

The client signs every outbound request with HMAC-SHA256 using a
composite key (`hmac_secret:api_key`). Replay protection uses a
timestamp tolerance window (default 300s).

## Decorator

The decorator is the recommended pattern. The function body is **never
executed** — after approval, the credential store + service handler
execute the action server-side.

```python
@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    pass

result = charge_customer(amount=120, customer="alice@example.com")
# {"status": "approved", "final_params": {...}, "execution": {...}}
```

### Async variant

```python
@kit.async_requires_approval(connection="stripe-prod", action="charge")
async def charge_customer(amount: int, customer: str):
    pass

result = await charge_customer(amount=120, customer="alice@example.com")
```

### Failure modes

The decorator raises `ApprovalDenied` when the approval is rejected
or times out. Wrap calls with try/except if the agent should respond
to denial:

```python
try:
    result = charge_customer(amount=5000, customer="…")
except ApprovalDenied as e:
    return f"Couldn't process: {e.reason}"
```

## Inline gate

For ad-hoc actions or when the decorator pattern doesn't fit:

```python
result = kit.gate(
    connection="github-main",
    action="deploy",
    params={"ref": "main", "env": "production"},
)
```

Returns the same payload as the decorator.

## Polling

`kit.gate` blocks until terminal by default. For long-running approvals
you can submit and check separately:

```python
job = kit.submit(connection="stripe-prod", action="charge",
                 params={"amount": 5000, "customer": "alice@example.com"})

while True:
    status = kit.status(job["id"])
    if status["state"] in ("approved", "rejected", "timeout", "blocked"):
        break
    time.sleep(1)
```

## MCP server

The SDK ships an MCP server so any MCP-compatible client (Claude
Desktop, IDE plugins) can mount ApprovalKit as a tool:

```bash
approvalkit-mcp
```

See `sdk/approvalkit/mcp_server.py` for the implementation.

## Reference

| Symbol | Description |
|--------|-------------|
| `ApprovalKit(base_url, api_key, hmac_secret, user_id=...)` | Client constructor. |
| `kit.requires_approval(connection, action)` | Sync decorator. |
| `kit.async_requires_approval(connection, action)` | Async decorator. |
| `kit.gate(connection, action, params)` | Inline blocking call. |
| `kit.submit(...)` / `kit.status(id)` | Non-blocking variant. |
| `ApprovalDenied` | Raised on rejection/timeout. |

The full source lives in [`sdk/approvalkit/`](https://github.com/yigitcankzl/ApprovalKit/tree/main/sdk/approvalkit).
