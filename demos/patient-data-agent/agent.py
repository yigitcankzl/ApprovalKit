"""
Demo Agent -- Patient Data Sharing
====================================
Simulates an AI healthcare agent that manages patient data sharing
requests: sharing with the patient's own doctor, external providers,
and insurance companies. Each level of sharing has different
approval requirements via ApprovalKit.

Rule configuration (set up via dashboard or setup_rules.py):

  gdrive-prod : share_own_doctor
    patient -> own doctor  -> no rule  (auto-approved)

  gdrive-prod : share_external
    to external provider   -> specific [attending_doctor]

  gdrive-prod : share_insurance
    to insurance company   -> all_of_n [patient, attending_doctor]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/patient-data-agent/agent.py
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
    user_id="auth0|patient_data_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

PATIENTS = [
    {"name": "Emily Carter", "id": "PAT-20451", "email": "emily.c@mail.com", "dob": "1988-05-14"},
    {"name": "Marcus Johnson", "id": "PAT-20523", "email": "marcus.j@mail.com", "dob": "1975-11-02"},
    {"name": "Sofia Rodriguez", "id": "PAT-20610", "email": "sofia.r@mail.com", "dob": "1992-08-21"},
]

DOCTORS = [
    {"name": "Dr. Sarah Kim", "email": "s.kim@hospital.org", "specialty": "Internal Medicine", "id": "DOC-301"},
    {"name": "Dr. James Obi", "email": "j.obi@cardiology-center.com", "specialty": "Cardiology", "id": "DOC-455"},
]

EXTERNAL_PROVIDERS = [
    {"name": "City Radiology Lab", "email": "records@cityradiology.com", "type": "diagnostic"},
    {"name": "Northside Physical Therapy", "email": "intake@northsidept.com", "type": "rehabilitation"},
]

INSURANCE_COMPANIES = [
    {"name": "BlueCross Health", "email": "claims@bluecross.com", "policy_prefix": "BCH"},
    {"name": "United Care", "email": "records@unitedcare.com", "policy_prefix": "UC"},
]

MEDICAL_RECORDS = {
    "PAT-20451": ["Lab results (2026-03-10)", "Annual physical (2026-01-15)", "Prescription history"],
    "PAT-20523": ["Cardiac stress test (2026-02-20)", "ECG results (2026-02-20)", "Medication list"],
    "PAT-20610": ["MRI scan (2026-03-05)", "Orthopedic assessment (2026-03-01)", "Surgical notes"],
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="gdrive-prod",
    action="share_own_doctor",
    params_fn=lambda patient_id, patient_name, doctor_name, doctor_email, records: {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "doctor_name": doctor_name,
        "doctor_email": doctor_email,
        "records_shared": records,
        "hipaa_compliant": True,
    },
)
def share_with_own_doctor(patient_id: str, patient_name: str,
                          doctor_name: str, doctor_email: str,
                          records: list) -> dict:
    """
    Share patient records with their attending doctor.
    Auto-approved -- standard care relationship, HIPAA-compliant.
    """
    return {"shared": True, "patient": patient_name, "doctor": doctor_name, "record_count": len(records)}


@kit.requires_approval(
    connection="gdrive-prod",
    action="share_external",
    params_fn=lambda patient_id, patient_name, provider_name, provider_email, provider_type, records, reason: {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "provider_name": provider_name,
        "provider_email": provider_email,
        "provider_type": provider_type,
        "records_shared": records,
        "clinical_reason": reason,
    },
)
def share_with_external_provider(patient_id: str, patient_name: str,
                                 provider_name: str, provider_email: str,
                                 provider_type: str, records: list,
                                 reason: str) -> dict:
    """
    Share patient records with an external provider.
    Requires attending doctor approval -- external data transfer.
    """
    return {"shared": True, "patient": patient_name, "provider": provider_name}


@kit.requires_approval(
    connection="gdrive-prod",
    action="share_insurance",
    params_fn=lambda patient_id, patient_name, insurance_name, insurance_email, records, claim_type: {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "insurance_company": insurance_name,
        "insurance_email": insurance_email,
        "records_shared": records,
        "claim_type": claim_type,
    },
)
def share_with_insurance(patient_id: str, patient_name: str,
                         insurance_name: str, insurance_email: str,
                         records: list, claim_type: str) -> dict:
    """
    Share patient records with insurance company for claims.
    Requires both patient consent and attending doctor approval (all_of_n).
    """
    return {"shared": True, "patient": patient_name, "insurance": insurance_name}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Patient Data Sharing Agent Demo")
    print("="*60)

    # Scenario 1: Share with own doctor -- auto-approved
    scenario("Scenario 1: Share with attending doctor -- auto-approved")
    pat = PATIENTS[0]
    doc = DOCTORS[0]
    records = MEDICAL_RECORDS[pat["id"]]
    try:
        result = share_with_own_doctor(
            pat["id"], pat["name"], doc["name"], doc["email"], records,
        )
        print(f"  Shared {result['record_count']} records: {result['patient']} -> {result['doctor']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Share with external provider -- doctor approval
    scenario("Scenario 2: Share with external provider -- doctor approval required")
    pat = PATIENTS[1]
    provider = EXTERNAL_PROVIDERS[0]
    records = MEDICAL_RECORDS[pat["id"]][:2]
    try:
        result = share_with_external_provider(
            pat["id"], pat["name"],
            provider["name"], provider["email"], provider["type"],
            records, "Cardiac imaging referral for stress test follow-up",
        )
        print(f"  Shared with {result['provider']} for {result['patient']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Share with insurance -- patient + doctor (all_of_n)
    scenario("Scenario 3: Share with insurance -- patient + doctor required")
    pat = PATIENTS[2]
    insurer = INSURANCE_COMPANIES[0]
    records = MEDICAL_RECORDS[pat["id"]]
    print("  Both patient consent and doctor approval required.")
    try:
        result = share_with_insurance(
            pat["id"], pat["name"],
            insurer["name"], insurer["email"],
            records, "Pre-authorization for orthopedic surgery",
        )
        print(f"  Shared with {result['insurance']} for {result['patient']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
