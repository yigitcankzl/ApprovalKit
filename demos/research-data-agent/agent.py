"""
Demo Agent -- Research Data Access
====================================
Simulates an AI agent that manages research data access requests:
anonymized data sets, patient-level data for studies, and external
data sharing with research partners. Each level requires different
approvals via ApprovalKit.

Rule configuration (set up via dashboard or setup_rules.py):

  gdrive-prod : anonymized
    de-identified data     -> no rule  (auto-approved)

  gdrive-prod : patient_level
    identifiable data      -> specific [ethics_board]

  gdrive-prod : external_share
    share with ext. org    -> all_of_n [ethics_board, chief_doctor]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/research-data-agent/agent.py
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
    user_id="auth0|research_data_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

RESEARCHERS = [
    {"name": "Dr. Lisa Wang", "email": "l.wang@hospital.org", "department": "Oncology", "id": "RES-101"},
    {"name": "Dr. Michael Torres", "email": "m.torres@hospital.org", "department": "Cardiology", "id": "RES-205"},
    {"name": "Dr. Aisha Patel", "email": "a.patel@hospital.org", "department": "Neurology", "id": "RES-312"},
]

STUDIES = [
    {
        "id": "STUDY-2026-001", "title": "Aggregate Outcomes in Post-Surgical Recovery",
        "type": "retrospective", "data_type": "anonymized",
        "patient_count": 2500, "irb_approved": True,
    },
    {
        "id": "STUDY-2026-014", "title": "Longitudinal Cardiac Biomarker Analysis",
        "type": "prospective", "data_type": "patient_level",
        "patient_count": 180, "irb_approved": True,
    },
    {
        "id": "STUDY-2026-027", "title": "Multi-Center Neurological Drug Trial",
        "type": "clinical_trial", "data_type": "patient_level",
        "patient_count": 450, "irb_approved": True,
    },
]

EXTERNAL_PARTNERS = [
    {"name": "Stanford Medical Research", "email": "data-sharing@stanford.edu", "type": "academic"},
    {"name": "PharmaCo R&D", "email": "clinical-data@pharmaco.com", "type": "pharmaceutical"},
]

DATA_SETS = {
    "STUDY-2026-001": {
        "tables": ["surgical_outcomes_anon", "recovery_metrics_anon", "demographics_agg"],
        "records": 2500, "size_gb": 1.2, "pii": False,
    },
    "STUDY-2026-014": {
        "tables": ["cardiac_biomarkers", "patient_history", "lab_results", "medications"],
        "records": 180, "size_gb": 4.8, "pii": True,
    },
    "STUDY-2026-027": {
        "tables": ["neuro_assessments", "drug_response", "adverse_events", "patient_demographics"],
        "records": 450, "size_gb": 12.5, "pii": True,
    },
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="gdrive-prod",
    action="anonymized",
    params_fn=lambda researcher_name, researcher_email, study_id, study_title, tables, record_count, size_gb: {
        "researcher_name": researcher_name,
        "researcher_email": researcher_email,
        "study_id": study_id,
        "study_title": study_title,
        "tables": tables,
        "record_count": record_count,
        "size_gb": size_gb,
        "contains_pii": False,
    },
)
def grant_anonymized_access(researcher_name: str, researcher_email: str,
                            study_id: str, study_title: str,
                            tables: list, record_count: int,
                            size_gb: float) -> dict:
    """
    Grant access to anonymized research data.
    Auto-approved -- de-identified data, no PII risk.
    """
    return {"access_granted": True, "researcher": researcher_name, "study": study_id, "tables": len(tables)}


@kit.requires_approval(
    connection="gdrive-prod",
    action="patient_level",
    params_fn=lambda researcher_name, researcher_email, study_id, study_title, tables, record_count, irb_approval: {
        "researcher_name": researcher_name,
        "researcher_email": researcher_email,
        "study_id": study_id,
        "study_title": study_title,
        "tables": tables,
        "record_count": record_count,
        "contains_pii": True,
        "irb_approved": irb_approval,
    },
)
def grant_patient_level_access(researcher_name: str, researcher_email: str,
                               study_id: str, study_title: str,
                               tables: list, record_count: int,
                               irb_approval: bool) -> dict:
    """
    Grant access to patient-level (identifiable) research data.
    Requires Ethics Board approval -- PII involved.
    """
    return {"access_granted": True, "researcher": researcher_name, "study": study_id, "records": record_count}


@kit.requires_approval(
    connection="gdrive-prod",
    action="external_share",
    params_fn=lambda researcher_name, study_id, study_title, partner_name, partner_email, partner_type, tables, record_count, data_use_agreement: {
        "researcher_name": researcher_name,
        "study_id": study_id,
        "study_title": study_title,
        "external_partner": partner_name,
        "partner_email": partner_email,
        "partner_type": partner_type,
        "tables_shared": tables,
        "record_count": record_count,
        "data_use_agreement": data_use_agreement,
        "contains_pii": True,
    },
)
def share_with_external_partner(researcher_name: str, study_id: str,
                                study_title: str, partner_name: str,
                                partner_email: str, partner_type: str,
                                tables: list, record_count: int,
                                data_use_agreement: bool) -> dict:
    """
    Share research data with an external organization.
    Requires both Ethics Board and Chief Doctor approval (all_of_n).
    """
    return {"shared": True, "study": study_id, "partner": partner_name, "records": record_count}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Research Data Access Agent Demo")
    print("="*60)

    # Scenario 1: Anonymized data access -- auto-approved
    scenario("Scenario 1: Anonymized data access -- auto-approved")
    researcher = RESEARCHERS[0]
    study = STUDIES[0]
    ds = DATA_SETS[study["id"]]
    try:
        result = grant_anonymized_access(
            researcher["name"], researcher["email"],
            study["id"], study["title"],
            ds["tables"], ds["records"], ds["size_gb"],
        )
        print(f"  Access granted to {result['researcher']}: {result['tables']} tables for {result['study']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Patient-level data -- Ethics Board approval
    scenario("Scenario 2: Patient-level data -- Ethics Board approval required")
    researcher = RESEARCHERS[1]
    study = STUDIES[1]
    ds = DATA_SETS[study["id"]]
    try:
        result = grant_patient_level_access(
            researcher["name"], researcher["email"],
            study["id"], study["title"],
            ds["tables"], ds["records"], study["irb_approved"],
        )
        print(f"  Access granted to {result['researcher']}: {result['records']} patient records for {result['study']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: External sharing -- Ethics Board + Chief Doctor (all_of_n)
    scenario("Scenario 3: External data sharing -- Ethics Board + Chief Doctor required")
    researcher = RESEARCHERS[2]
    study = STUDIES[2]
    ds = DATA_SETS[study["id"]]
    partner = EXTERNAL_PARTNERS[1]
    print("  Both Ethics Board and Chief Doctor must approve.")
    try:
        result = share_with_external_partner(
            researcher["name"], study["id"], study["title"],
            partner["name"], partner["email"], partner["type"],
            ds["tables"], ds["records"], True,
        )
        print(f"  Shared with {result['partner']}: {result['records']} records for {result['study']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
