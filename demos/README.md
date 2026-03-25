# ApprovalKit — Demo Agents

Two fully working demo agents that show ApprovalKit in action.

## Setup

```bash
# 1. Install the SDK
pip install ../sdk

# 2. Set credentials (from scripts/setup.py output)
export APPROVALKIT_URL=http://localhost:8000
export APPROVALKIT_API_KEY=<your-api-key>
export APPROVALKIT_HMAC_SECRET=<your-hmac-secret>

# 3. Create all connections, approvers, and rules in one shot
python demos/setup_rules.py
```

---

## Agent 1 — E-Commerce (`ecommerce_agent.py`)

Simulates a shopping agent that charges customers, issues refunds,
and posts to Slack.

```bash
python demos/ecommerce_agent.py
```

| Scenario | Action | Rule |
|----------|--------|------|
| Small order $49 | `stripe-prod:charge` | No rule — auto-approved |
| Medium order $349 | `stripe-prod:charge` | `any_one` → sales_manager |
| Large order $5,000 | `stripe-prod:charge` | `all_of_n` → sales_manager + CFO |
| Refund $340 | `stripe-prod:refund` | `specific` → cs_manager (partial approval) |
| Slack #finance | `slack-prod:send_message` | `specific` → CFO |

---

## Agent 2 — HR (`hr_agent.py`)

Simulates an HR assistant that sends emails, manages Slack channels,
and handles GitHub org membership during onboarding/offboarding.

```bash
python demos/hr_agent.py
```

| Scenario | Action | Rule |
|----------|--------|------|
| Interview invite | `gmail-prod:send_email` | No rule — auto-approved |
| Offer letter | `gmail-prod:send_email` | `specific` → hr_manager |
| Termination letter | `gmail-prod:send_email` | `all_of_n` → hr_manager + CEO |
| Slack #hr | `slack-prod:send_message` | `specific` → hr_manager |
| GitHub add member | `github-prod:add_member` | `specific` → it_manager |
| GitHub add admin | `github-prod:add_member` | `all_of_n` → it_manager + CTO |
| GitHub remove member | `github-prod:remove_member` | `all_of_n` → it_manager + hr_manager |

---

## Files

```
demos/
├── setup_rules.py      # Creates all connections, approvers, rules via API
├── ecommerce_agent.py  # E-commerce demo agent
├── hr_agent.py         # HR demo agent
└── README.md
```

After running either demo, check the audit log at `http://localhost:3000/audit`.
