"""
Demo Agent — Scholarship (Education)
=====================================
Simulates an AI agent that processes scholarship applications,
awards, and full-ride scholarships with escalating approval tiers.

Rule configuration:

  scholarship-mgmt : scholarship
    type=application       -> no rule  (auto-approved)
    type=award             -> any_one  [committee]
    type=full_scholarship  -> all_of_n [rector, committee]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/scholarship-agent/agent.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdk"))

from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url=os.environ.get("APPROVALKIT_URL", "http://localhost:8000"),
    api_key=os.environ.get("APPROVALKIT_API_KEY", ""),
    hmac_secret=os.environ.get("APPROVALKIT_HMAC_SECRET", ""),
    user_id="auth0|scholarship_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

APPLICANTS = {
    "APP-2001": {"name": "Diana Park", "gpa": 3.92, "major": "Biology", "year": "Junior"},
    "APP-2002": {"name": "Ethan Nguyen", "gpa": 3.78, "major": "Computer Science", "year": "Sophomore"},
    "APP-2003": {"name": "Fatima Al-Rashid", "gpa": 3.98, "major": "Physics", "year": "Senior"},
}

SCHOLARSHIPS = {
    "merit-500": {"name": "Merit Award", "amount_usd": 500},
    "stem-5000": {"name": "STEM Excellence Award", "amount_usd": 5000},
    "full-ride": {"name": "Presidential Full Scholarship", "amount_usd": 48000},
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="scholarship-mgmt",
    action="scholarship",
    params_fn=lambda applicant_id, scholarship_id: {
        "applicant_id": applicant_id,
        "applicant_name": APPLICANTS[applicant_id]["name"],
        "gpa": APPLICANTS[applicant_id]["gpa"],
        "major": APPLICANTS[applicant_id]["major"],
        "scholarship": SCHOLARSHIPS[scholarship_id]["name"],
        "type": "application",
    },
)
def submit_application(applicant_id: str, scholarship_id: str) -> dict:
    """
    Log a scholarship application.
    Auto-approved -- records the application in the system.
    """
    applicant = APPLICANTS[applicant_id]
    scholarship = SCHOLARSHIPS[scholarship_id]
    return {
        "applicant": applicant["name"],
        "scholarship": scholarship["name"],
        "status": "application_received",
    }


@kit.requires_approval(
    connection="scholarship-mgmt",
    action="scholarship",
    params_fn=lambda applicant_id, scholarship_id, justification: {
        "applicant_id": applicant_id,
        "applicant_name": APPLICANTS[applicant_id]["name"],
        "gpa": APPLICANTS[applicant_id]["gpa"],
        "scholarship": SCHOLARSHIPS[scholarship_id]["name"],
        "amount_usd": SCHOLARSHIPS[scholarship_id]["amount_usd"],
        "type": "award",
        "justification": justification,
    },
)
def award_scholarship(applicant_id: str, scholarship_id: str, justification: str) -> dict:
    """
    Award a standard scholarship.
    Requires committee approval.
    """
    applicant = APPLICANTS[applicant_id]
    scholarship = SCHOLARSHIPS[scholarship_id]
    return {
        "applicant": applicant["name"],
        "scholarship": scholarship["name"],
        "amount_usd": scholarship["amount_usd"],
        "status": "awarded",
    }


@kit.requires_approval(
    connection="scholarship-mgmt",
    action="scholarship",
    params_fn=lambda applicant_id, justification: {
        "applicant_id": applicant_id,
        "applicant_name": APPLICANTS[applicant_id]["name"],
        "gpa": APPLICANTS[applicant_id]["gpa"],
        "major": APPLICANTS[applicant_id]["major"],
        "year": APPLICANTS[applicant_id]["year"],
        "scholarship": SCHOLARSHIPS["full-ride"]["name"],
        "amount_usd": SCHOLARSHIPS["full-ride"]["amount_usd"],
        "type": "full_scholarship",
        "justification": justification,
    },
)
def grant_full_scholarship(applicant_id: str, justification: str) -> dict:
    """
    Grant a full-ride scholarship.
    Requires both rector AND committee approval (all_of_n).
    """
    applicant = APPLICANTS[applicant_id]
    scholarship = SCHOLARSHIPS["full-ride"]
    return {
        "applicant": applicant["name"],
        "scholarship": scholarship["name"],
        "amount_usd": scholarship["amount_usd"],
        "status": "full_scholarship_granted",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Scholarship Agent Demo")
    print("="*60)

    # -- Scenario 1: Application submission -- auto-approved ---
    scenario("Scenario 1: Application submission -- auto-approved")
    try:
        result = submit_application("APP-2001", "stem-5000")
        print(f"  {result['applicant']} applied for {result['scholarship']}")
        print(f"  Status: {result['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Scholarship award -- committee approves ---
    scenario("Scenario 2: Award $5,000 STEM scholarship -- waiting for committee")
    try:
        result = award_scholarship(
            "APP-2002", "stem-5000",
            "Outstanding research project in ML; top 5% of class"
        )
        print(f"  Awarded: {result['applicant']} -- {result['scholarship']}")
        print(f"  Amount: ${result['amount_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Full scholarship -- rector + committee ---
    scenario("Scenario 3: Full scholarship ($48,000) -- rector + committee")
    print("  Both rector and committee must approve.")
    try:
        result = grant_full_scholarship(
            "APP-2003",
            "Highest GPA in Physics department; published 3 papers; national award winner"
        )
        print(f"  Granted: {result['applicant']} -- {result['scholarship']}")
        print(f"  Amount: ${result['amount_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
