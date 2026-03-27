"""
Demo Agent -- Prescription Refill
===================================
Simulates an AI pharmacy agent that processes prescription refills:
routine refills, controlled substance refills, and dosage changes.
Each category has different approval gates via ApprovalKit.

Rule configuration (set up via dashboard or setup_rules.py):

  gmail-prod : routine_refill
    standard medication    -> no rule  (auto-approved)

  gmail-prod : controlled_substance
    schedule II-V          -> specific [prescribing_doctor]

  gmail-prod : dosage_change
    any dosage adjustment  -> all_of_n [prescribing_doctor, pharmacist]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/prescription-refill-agent/agent.py
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
    user_id="auth0|prescription_refill_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

PATIENTS = [
    {"name": "Maria Santos", "id": "PAT-30112", "email": "maria.s@mail.com", "dob": "1965-03-22"},
    {"name": "David Lee", "id": "PAT-30245", "email": "david.l@mail.com", "dob": "1980-07-10"},
    {"name": "Helen Brooks", "id": "PAT-30389", "email": "helen.b@mail.com", "dob": "1958-12-05"},
]

PRESCRIPTIONS = {
    "PAT-30112": {
        "rx_id": "RX-88010", "medication": "Lisinopril", "dosage": "10mg",
        "frequency": "once daily", "refills_remaining": 3, "schedule": "non-controlled",
        "prescriber": "Dr. Sarah Kim",
    },
    "PAT-30245": {
        "rx_id": "RX-88042", "medication": "Adderall", "dosage": "20mg",
        "frequency": "once daily", "refills_remaining": 0, "schedule": "II",
        "prescriber": "Dr. James Obi",
    },
    "PAT-30389": {
        "rx_id": "RX-88071", "medication": "Metoprolol", "dosage": "50mg",
        "frequency": "twice daily", "refills_remaining": 2, "schedule": "non-controlled",
        "prescriber": "Dr. Sarah Kim",
    },
}

PHARMACIES = [
    {"name": "CityPharm Main", "id": "PHRM-01", "pharmacist": "Dr. Amy Chen"},
    {"name": "HealthMart Express", "id": "PHRM-02", "pharmacist": "Dr. Robert Hall"},
]

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="gmail-prod",
    action="routine_refill",
    params_fn=lambda patient_id, patient_name, rx_id, medication, dosage, frequency, pharmacy_name: {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "rx_id": rx_id,
        "medication": medication,
        "dosage": dosage,
        "frequency": frequency,
        "pharmacy": pharmacy_name,
    },
)
def process_routine_refill(patient_id: str, patient_name: str,
                           rx_id: str, medication: str, dosage: str,
                           frequency: str, pharmacy_name: str) -> dict:
    """
    Process routine prescription refill.
    Auto-approved -- non-controlled medication with refills remaining.
    """
    return {"refilled": True, "patient": patient_name, "medication": medication, "dosage": dosage}


@kit.requires_approval(
    connection="gmail-prod",
    action="controlled_substance",
    params_fn=lambda patient_id, patient_name, rx_id, medication, dosage, schedule, prescriber, last_fill_date: {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "rx_id": rx_id,
        "medication": medication,
        "dosage": dosage,
        "dea_schedule": schedule,
        "prescriber": prescriber,
        "last_fill_date": last_fill_date,
    },
)
def refill_controlled_substance(patient_id: str, patient_name: str,
                                rx_id: str, medication: str, dosage: str,
                                schedule: str, prescriber: str,
                                last_fill_date: str) -> dict:
    """
    Refill a controlled substance prescription.
    Requires prescribing doctor approval -- DEA-regulated.
    """
    return {"refilled": True, "patient": patient_name, "medication": medication, "schedule": schedule}


@kit.requires_approval(
    connection="gmail-prod",
    action="dosage_change",
    params_fn=lambda patient_id, patient_name, rx_id, medication, current_dosage, new_dosage, reason, prescriber: {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "rx_id": rx_id,
        "medication": medication,
        "current_dosage": current_dosage,
        "new_dosage": new_dosage,
        "clinical_reason": reason,
        "prescriber": prescriber,
    },
)
def request_dosage_change(patient_id: str, patient_name: str,
                          rx_id: str, medication: str,
                          current_dosage: str, new_dosage: str,
                          reason: str, prescriber: str) -> dict:
    """
    Request a dosage change for an existing prescription.
    Requires both prescribing doctor and pharmacist approval (all_of_n).
    """
    return {"changed": True, "patient": patient_name, "medication": medication, "new_dosage": new_dosage}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Prescription Refill Agent Demo")
    print("="*60)

    # Scenario 1: Routine refill -- auto-approved
    scenario("Scenario 1: Routine refill (Lisinopril 10mg) -- auto-approved")
    pat = PATIENTS[0]
    rx = PRESCRIPTIONS[pat["id"]]
    pharmacy = PHARMACIES[0]
    try:
        result = process_routine_refill(
            pat["id"], pat["name"], rx["rx_id"],
            rx["medication"], rx["dosage"], rx["frequency"],
            pharmacy["name"],
        )
        print(f"  Refilled: {result['medication']} {result['dosage']} for {result['patient']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Controlled substance -- prescribing doctor approval
    scenario("Scenario 2: Controlled substance (Adderall Schedule II) -- doctor required")
    pat = PATIENTS[1]
    rx = PRESCRIPTIONS[pat["id"]]
    try:
        result = refill_controlled_substance(
            pat["id"], pat["name"], rx["rx_id"],
            rx["medication"], rx["dosage"], rx["schedule"],
            rx["prescriber"], "2026-02-27",
        )
        print(f"  Refilled: {result['medication']} (Schedule {result['schedule']}) for {result['patient']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Dosage change -- doctor + pharmacist (all_of_n)
    scenario("Scenario 3: Dosage change (Metoprolol 50mg->100mg) -- doctor + pharmacist required")
    pat = PATIENTS[2]
    rx = PRESCRIPTIONS[pat["id"]]
    print("  Both prescribing doctor and pharmacist must approve.")
    try:
        result = request_dosage_change(
            pat["id"], pat["name"], rx["rx_id"],
            rx["medication"], rx["dosage"], "100mg",
            "Blood pressure not adequately controlled at current dose",
            rx["prescriber"],
        )
        print(f"  Dosage changed: {result['medication']} -> {result['new_dosage']} for {result['patient']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
