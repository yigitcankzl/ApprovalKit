# TravelOps Agent — WITHOUT ApprovalKit (Unsafe Version)

This is the **unsafe** version of TravelOps. The agent has direct access
to API keys and executes all actions without human approval.

**This version exists purely for comparison.** Run both side-by-side to
see why human-in-the-loop approval matters for AI agents.

## Comparison

| | Without ApprovalKit | With ApprovalKit |
|---|---|---|
| Credentials | Agent holds Stripe API key | Agent never sees credentials |
| $349 flight | Charged immediately | Manager approves via Guardian push |
| $3200 flight | Charged immediately | Step-up: Manager + CFO both approve |
| Wrong amount | Money gone, no recourse | Approver catches it before charge |
| Audit trail | None | Full audit log with timestamps |
| Revocation | Must rotate API key | Revoke from dashboard instantly |
| Scope creep | Agent can charge anything | Alert on new action types |

## Run

```bash
# Unsafe version — no ApprovalKit
python agents/travelops/without-approvalkit/agent.py --dest "new york" --flight-price 3200

# Safe version — with ApprovalKit
python agents/travelops/agent.py --dest "new york" --flight-price 3200
```

## Output comparison

**Without ApprovalKit:**
```
[1/7] Flight: Delta DL34 (economy) — $3200
      NO APPROVAL NEEDED — charging immediately
      [STRIPE] Charging $3200
      [STRIPE] API Key: sk_test_51TE... (EXPOSED TO AGENT)
      Charged. No one reviewed this.

  RISKS:
  - HIGH VALUE: $3200 charge had NO step-up authentication
  - Agent could charge ANY amount — no guardrails
  - Stripe API key exposed in agent memory
```

**With ApprovalKit:**
```
[1/7] Flight: Delta DL34 (economy) — $3200
[ApprovalKit] stripe-prod/charge → Step-up triggered (any_one → all_of_n)
[ApprovalKit] Pending — Guardian push sent to Manager + CFO
[ApprovalKit] Approved — Token Vault executed server-side
      Approved — flight booked. Agent never saw Stripe key.
```
