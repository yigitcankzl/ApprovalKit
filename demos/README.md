# ApprovalKit — Demo Agents

Six demo agents covering every use case from the gallery.
Each agent maps directly to a real-world scenario with realistic
approval rules.

## Setup

```bash
# 1. Install SDK
pip install ../sdk

# 2. Set credentials (from scripts/setup.py output)
export APPROVALKIT_URL=http://localhost:8000
export APPROVALKIT_API_KEY=<key>
export APPROVALKIT_HMAC_SECRET=<secret>

# 3. Create all rules in one shot
python demos/setup_rules.py

# 4. Run any demo
python demos/ecommerce_agent.py
python demos/hr_agent.py
python demos/devops_agent.py
python demos/opensource_agent.py
python demos/research_agent.py
python demos/fintech_agent.py
python demos/comms_agent.py
```

---

## Agent 1 — E-Commerce (`ecommerce_agent.py`)

Stripe payments with tiered approvals + partial refund approval.

| Scenario | Action | Rule |
|----------|--------|------|
| Small order $49 | `stripe-prod:charge` | Auto-approved |
| Medium order $349 | `stripe-prod:charge` | `any_one` → sales_manager |
| Large order $5,000 | `stripe-prod:charge` | `all_of_n` → sales_manager + CFO |
| Refund $340 | `stripe-prod:refund` | `specific` → cs_manager (partial approval) |
| Slack #finance | `slack-prod:send_message` | `specific` → CFO |

---

## Agent 2 — HR (`hr_agent.py`)

Email, Slack, and GitHub org management across onboarding/offboarding.

| Scenario | Action | Rule |
|----------|--------|------|
| Interview invite | `gmail-prod:send_email` | Auto-approved |
| Offer letter | `gmail-prod:send_email` | `specific` → hr_manager |
| Termination letter | `gmail-prod:send_email` | `all_of_n` → hr_manager + CEO |
| Slack #hr | `slack-prod:send_message` | `specific` → hr_manager |
| GitHub add member | `github-prod:add_member` | `specific` → it_manager |
| GitHub add admin | `github-prod:add_member` | `all_of_n` → it_manager + CTO |
| GitHub remove member | `github-prod:remove_member` | `all_of_n` → it_manager + hr_manager |

---

## Agent 3 — DevOps (`devops_agent.py`)

GitHub deployments with environment-based rules and blackout windows.

| Scenario | Action | Rule |
|----------|--------|------|
| Deploy to staging | `github-main:deploy` | Auto-approved |
| Deploy to production | `github-main:deploy` | `any_one` → maintainer |
| Production rollback | `github-main:rollback` | `specific` → lead only |

---

## Agent 4 — Open Source (`opensource_agent.py`)

Multi-maintainer governance: k-of-n voting, npm publishing, treasury.

| Scenario | Action | Rule |
|----------|--------|------|
| Small PR (42 lines) | `github-main:merge_pr` | Auto-merged |
| Large PR (380 lines) | `github-main:merge_pr` | `k_of_n` k=2/3 → maintainers |
| npm patch publish | `npm-registry:publish` | `specific` → lead_maintainer |
| npm major publish | `npm-registry:publish` | `k_of_n` k=2/3 → maintainers |
| Treasury payout $80 | `stripe-prod:payout` | `specific` → treasurer |
| Treasury payout $500 | `stripe-prod:payout` | `all_of_n` → treasurer + lead |

---

## Agent 5 — Research Lab (`research_agent.py`)

AWS compute provisioning, paper submission, and grant spending controls.

| Scenario | Action | Rule |
|----------|--------|------|
| Compute $12 | `aws-lab:provision_compute` | Auto-approved |
| Compute $65 | `aws-lab:provision_compute` | `any_one` → PI |
| Compute $420 | `aws-lab:provision_compute` | `all_of_n` → PI + Finance |
| Paper submission | `arxiv:submit_paper` | `all_of_n` → all co-authors |
| Grant spend $1,200 | `stripe-prod:charge` | `all_of_n` → PI + Finance |

---

## Agent 6 — Financial Services (`fintech_agent.py`)

Payment processing with a full compliance chain.

| Scenario | Action | Rule |
|----------|--------|------|
| Payout $4,500 | `stripe-prod:payout` | `any_one` → manager |
| Payout $85,000 | `stripe-prod:payout` | `sequential` → manager → compliance → CFO |
| New vendor payment | `stripe-prod:vendor_payment` | `all_of_n` → procurement + legal |
| Wire transfer $250k | `stripe-prod:wire_transfer` | `sequential` → ops → finance → CFO |

---

## Agent 7 — Communications (`comms_agent.py`)

Email campaigns, Slack announcements, and press releases.

| Scenario | Action | Rule |
|----------|--------|------|
| Internal email (8) | `gmail-prod:send_email` | Auto-approved |
| Client newsletter (45) | `gmail-prod:send_email` | `any_one` → manager |
| Mass email (12,500) | `gmail-prod:send_email` | `sequential` → marketing_lead → legal |
| Slack #announcements | `slack-prod:send_message` | `specific` → CEO |
| Press release | `gmail-prod:press_release` | `sequential` → PR Manager → Legal → CEO |

---

After any demo, check the audit log: `http://localhost:3000/audit`
