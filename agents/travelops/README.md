# TravelOps Agent — Corporate Travel Manager

AI agent that manages end-to-end business travel through ApprovalKit.
Every financial transaction requires human approval via Auth0 Guardian push.

## What it does

When an employee says "I'm going to Berlin for a conference", the agent:

| Step | Action | Service | Approval |
|------|--------|---------|----------|
| 1 | Book flight | Stripe (charge) | < $500 auto, $500-2000 manager, > $2000 manager + CFO |
| 2 | Reserve hotel | Stripe (charge) | < $150/night auto, > $150 manager |
| 3 | Buy travel insurance | Stripe (charge) | Auto (always < $120) |
| 4 | Add to calendar | Google Calendar | Auto |
| 5 | Notify team | Slack | Auto |
| 6 | Log expense | Internal | Auto |
| 7 | Visa reminder | Gmail | Auto |

## Quick start

```bash
# From ApprovalKit root
export APPROVALKIT_URL=http://localhost:8000
export APPROVALKIT_API_KEY=<your key>
export APPROVALKIT_HMAC_SECRET=<your secret>

# Economy flight to Berlin, 3 nights
python agents/travelops/agent.py

# Business class to New York (triggers step-up)
python agents/travelops/agent.py --dest "new york" --class business --nights 5

# Expensive trip (CFO approval required)
python agents/travelops/agent.py --dest "san francisco" --flight-price 3800 --hotel-price 490 --nights 4
```

## Demo scenarios

### Scenario 1: Budget trip (auto-approve)
```bash
python agents/travelops/agent.py --dest berlin --flight-price 420 --hotel-price 95
```
Flight $420 + Hotel $285 = $705 total. Flight auto-approves (< $500 rule or no rule).

### Scenario 2: Mid-range trip (manager approval)
```bash
python agents/travelops/agent.py --dest london --flight-price 1400 --class business
```
Business class $1400 → manager gets Guardian push → approves → booked.

### Scenario 3: Expensive trip (step-up CFO)
```bash
python agents/travelops/agent.py --dest "new york" --flight-price 3200 --hotel-price 650 --nights 5 --class business
```
Flight $3200 → step-up → manager AND CFO must both approve.
Hotel $650/night → manager approval per night.

### Scenario 4: Visa required
```bash
python agents/travelops/agent.py --dest "new york" --purpose "AWS re:Invent"
```
New York requires visa → agent sends Gmail reminder automatically.

## Architecture

```
Employee request
    │
    ▼
TravelOps Agent (this script)
    │
    ├── search_flights() → simulated flight DB
    ├── search_hotels() → simulated hotel DB
    ├── recommend_insurance() → insurance plans
    │
    ▼
ApprovalKit SDK (@kit.requires_approval decorator)
    │
    ├── POST /api/v1/request → Rule Engine
    │   ├── amount < $500 → auto-approve
    │   ├── amount $500-$2000 → any_one (manager)
    │   └── amount > $2000 → step-up all_of_n (manager + CFO)
    │
    ▼
Auth0 CIBA → Guardian push to manager/CFO phone
    │
    ▼
Auth0 Token Vault → Stripe charge executed
    │
    ▼
Agent continues to next step
```

## Required ApprovalKit setup

The agent needs these connections and rules in ApprovalKit:

**Connections:** stripe-prod, slack-prod, gmail-prod
**Approvers:** Manager, CFO (with Guardian linked)
**Rules:** Set up via Agent Demos page → E-Commerce Agent → "Setup Demo"
