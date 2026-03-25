"""
Demo Agent — Research Lab
=========================
Simulates an AI research assistant that provisions compute,
submits papers, and manages grant spending.
Small compute jobs are auto-approved. Large budgets require the PI.
Publication requires all co-authors.

Rules:
  aws-lab : provision_compute
    amount <= 20    → no rule (auto)
    amount > 20     → any_one [pi]
    amount > 100    → all_of_n [pi, finance_dept]

  arxiv : submit_paper
    (any)           → all_of_n [all co-authors listed in params]

  stripe-prod : charge
    purpose=grant   → all_of_n [pi, finance_dept]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/research_agent.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))
from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url=os.environ.get("APPROVALKIT_URL", "http://localhost:8000"),
    api_key=os.environ.get("APPROVALKIT_API_KEY", ""),
    hmac_secret=os.environ.get("APPROVALKIT_HMAC_SECRET", ""),
    user_id="auth0|research_agent",
    poll_interval=3,
    timeout=180,
)

# ── Actions ───────────────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="aws-lab",
    action="provision_compute",
    params_fn=lambda instance_type, hours, project, estimated_cost: {
        "instance_type": instance_type,
        "hours": hours,
        "project": project,
        "estimated_cost_usd": estimated_cost,
    },
)
def provision_compute(instance_type: str, hours: int, project: str, estimated_cost: float) -> dict:
    """Provision AWS compute for a research job."""
    return {"provisioned": instance_type, "hours": hours, "project": project}


@kit.requires_approval(
    connection="arxiv",
    action="submit_paper",
    params_fn=lambda title, authors, journal, abstract: {
        "title": title,
        "authors": authors,
        "target_journal": journal,
        "abstract_preview": abstract[:150] + ("..." if len(abstract) > 150 else ""),
    },
)
def submit_paper(title: str, authors: list, journal: str, abstract: str) -> dict:
    """Submit a paper to a journal. All co-authors must approve."""
    return {"submitted": title, "journal": journal}


@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda amount, project, purpose: {
        "amount_usd": amount,
        "project": project,
        "purpose": purpose,
    },
)
def grant_spend(amount: float, project: str, purpose: str) -> dict:
    """Spend from a research grant. PI + finance must approve."""
    return {"spent": amount, "project": project}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Research Lab Agent Demo")
    print("="*60)

    scenario("Scenario 1: Small compute job ($12) — auto-approved")
    try:
        result = provision_compute("t3.medium", 4, "nlp-experiment-42", 12.0)
        print(f"  Provisioned {result['provisioned']} for {result['hours']}h ({result['project']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 2: Medium compute ($65) — PI approval required")
    try:
        result = provision_compute("p3.2xlarge", 8, "llm-training-run", 65.0)
        print(f"  Provisioned {result['provisioned']} for {result['hours']}h ({result['project']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 3: Large compute ($420) — PI + Finance dept (all_of_n)")
    print("  Both PI and Finance must approve.")
    try:
        result = provision_compute("p4d.24xlarge", 24, "foundation-model-training", 420.0)
        print(f"  Provisioned {result['provisioned']} for {result['hours']}h ({result['project']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 4: Paper submission — all co-authors must approve")
    print("  All 3 co-authors notified simultaneously.")
    try:
        result = submit_paper(
            title="Efficient Human-in-the-Loop Approval for Autonomous AI Agents",
            authors=["Dr. Smith", "Dr. Jones", "Dr. Lee"],
            journal="NeurIPS 2026",
            abstract=(
                "We present ApprovalKit, a middleware platform enabling fine-grained "
                "human oversight of AI agent actions using Auth0 CIBA, Token Vault, and FGA."
            ),
        )
        print(f"  Submitted '{result['submitted']}' to {result['journal']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 5: Grant spend $1,200 — PI + Finance (all_of_n)")
    print("  Large grant disbursement requires dual sign-off.")
    try:
        result = grant_spend(1200.0, "NIH-2025-003", "Conference travel + accommodation")
        print(f"  Spent ${result['spent']} on {result['project']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
