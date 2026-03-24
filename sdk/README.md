# approvalkit

Human approval middleware for AI agents.

## Install

```bash
# from PyPI (once published)
pip install approvalkit

# or directly from the repo
pip install ./sdk
```

## Usage

```python
from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url="http://localhost:8000",
    api_key="your-api-key",
    hmac_secret="your-hmac-secret",
)

@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    stripe.charge(amount=amount, customer=customer)
```

See the full docs at `http://localhost:3000/docs`.
