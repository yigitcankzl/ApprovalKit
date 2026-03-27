"""
Demo Agent — GDPR Request (Legal)
==================================
Simulates an AI agent that handles GDPR data subject requests
including logging, single-record deletion, and bulk deletions.

Rule configuration:

  gdpr-portal : data_request
    type=request_log     -> no rule  (auto-approved)
    type=single_delete   -> any_one  [privacy_officer]
    type=bulk_delete     -> all_of_n [CTO, privacy_officer]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/gdpr-request-agent/agent.py
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
    user_id="auth0|gdpr_request_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

DATA_SUBJECTS = {
    "DS-5001": {"name": "Hans Mueller", "email": "hans@example.de", "records": 14, "region": "EU-DE"},
    "DS-5002": {"name": "Marie Dupont", "email": "marie@example.fr", "records": 47, "region": "EU-FR"},
    "DS-5003": {"name": "Bulk request", "email": "compliance@corp.eu", "records": 2340, "region": "EU-wide"},
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="gdpr-portal",
    action="data_request",
    params_fn=lambda subject_id, request_type_detail: {
        "subject_id": subject_id,
        "subject_name": DATA_SUBJECTS[subject_id]["name"],
        "email": DATA_SUBJECTS[subject_id]["email"],
        "region": DATA_SUBJECTS[subject_id]["region"],
        "type": "request_log",
        "request_detail": request_type_detail,
    },
)
def log_data_request(subject_id: str, request_type_detail: str) -> dict:
    """
    Log a GDPR data subject request.
    Auto-approved -- creates an audit trail entry.
    """
    subject = DATA_SUBJECTS[subject_id]
    return {
        "subject": subject["name"],
        "request": request_type_detail,
        "status": "logged",
    }


@kit.requires_approval(
    connection="gdpr-portal",
    action="data_request",
    params_fn=lambda subject_id, justification: {
        "subject_id": subject_id,
        "subject_name": DATA_SUBJECTS[subject_id]["name"],
        "email": DATA_SUBJECTS[subject_id]["email"],
        "records_affected": DATA_SUBJECTS[subject_id]["records"],
        "region": DATA_SUBJECTS[subject_id]["region"],
        "type": "single_delete",
        "justification": justification,
    },
)
def delete_single_record(subject_id: str, justification: str) -> dict:
    """
    Delete a single data subject's records.
    Requires privacy_officer approval.
    """
    subject = DATA_SUBJECTS[subject_id]
    return {
        "subject": subject["name"],
        "records_deleted": subject["records"],
        "status": "deleted",
    }


@kit.requires_approval(
    connection="gdpr-portal",
    action="data_request",
    params_fn=lambda subject_id, justification: {
        "subject_id": subject_id,
        "description": DATA_SUBJECTS[subject_id]["name"],
        "records_affected": DATA_SUBJECTS[subject_id]["records"],
        "region": DATA_SUBJECTS[subject_id]["region"],
        "type": "bulk_delete",
        "justification": justification,
    },
)
def bulk_delete_records(subject_id: str, justification: str) -> dict:
    """
    Bulk deletion of data records across systems.
    Requires both CTO AND privacy_officer approval (all_of_n).
    """
    subject = DATA_SUBJECTS[subject_id]
    return {
        "description": subject["name"],
        "records_deleted": subject["records"],
        "region": subject["region"],
        "status": "bulk_deleted",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  GDPR Request Agent Demo")
    print("="*60)

    # -- Scenario 1: Request log -- auto-approved ---
    scenario("Scenario 1: Log data access request -- auto-approved")
    try:
        result = log_data_request("DS-5001", "Subject access request (Art. 15)")
        print(f"  Logged request for {result['subject']}")
        print(f"  Status: {result['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Single delete -- privacy_officer ---
    scenario("Scenario 2: Single record deletion (47 records) -- privacy_officer")
    try:
        result = delete_single_record(
            "DS-5002",
            "Right to erasure request (Art. 17); identity verified"
        )
        print(f"  Deleted data for {result['subject']}")
        print(f"  Records removed: {result['records_deleted']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Bulk delete -- CTO + privacy_officer ---
    scenario("Scenario 3: Bulk deletion (2,340 records) -- CTO + privacy_officer")
    print("  Both CTO and privacy_officer must approve.")
    try:
        result = bulk_delete_records(
            "DS-5003",
            "EU-wide compliance mandate; regulatory deadline 2025-12-31"
        )
        print(f"  Bulk deletion complete: {result['description']}")
        print(f"  Records removed: {result['records_deleted']:,}")
        print(f"  Region: {result['region']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
