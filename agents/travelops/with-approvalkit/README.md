# TravelOps Agent — WITH ApprovalKit (Safe Version)

This is the **safe** version. The agent never holds credentials.
Every financial action goes through ApprovalKit for human approval
via Auth0 Guardian push notifications. Tokens are retrieved from
Auth0 Token Vault only after approval.

## How it works

```
Agent: "Book $3200 flight to NYC"
  |
  v
ApprovalKit: Rule matched → step-up (amount > $2000)
  |
  v
Guardian Push → Manager's phone + CFO's phone
  |
  v
Both approve → Auth0 Token Vault retrieves Stripe token
  |
  v
Stripe charge executed. Agent never saw the API key.
```

## Run

```bash
export APPROVALKIT_URL=http://localhost:8000
export APPROVALKIT_API_KEY=<your key>
export APPROVALKIT_HMAC_SECRET=<your secret>

# Budget trip (auto-approve)
python agent.py --dest berlin --flight-price 420

# Expensive trip (step-up: manager + CFO)
python agent.py --dest "new york" --flight-price 3200 --class business

# All 4 scenarios
python scenarios.py
```
