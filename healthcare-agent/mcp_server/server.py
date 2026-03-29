"""
Healthcare AI Agent — MCP Server
==================================
Exposes healthcare operations as MCP tools for Claude Desktop and other
MCP-compatible AI agents. All high-stakes actions go through ApprovalKit.

Usage:
    python -m mcp_server.server

Claude Desktop config:
    {
      "mcpServers": {
        "healthcare-agent": {
          "command": "python",
          "args": ["-m", "mcp_server.server"],
          "env": {
            "HEALTHCARE_API_URL": "http://localhost:3002"
          }
        }
      }
    }
"""
import json
import os
from typing import Any

import httpx

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError("MCP SDK not installed. Run: pip install mcp")

API_URL = os.environ.get("HEALTHCARE_API_URL", "http://localhost:3002").rstrip("/")

mcp = FastMCP(
    "HealthcareAgent",
    description=(
        "HIPAA-compliant healthcare management agent. "
        "Manages patients, prescriptions, billing, referrals, and emergencies. "
        "All sensitive actions require human approval via ApprovalKit."
    ),
)


async def _api(method: str, path: str, body: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        if method == "GET":
            r = await client.get(f"{API_URL}{path}")
        elif method == "POST":
            r = await client.post(f"{API_URL}{path}", json=body)
        elif method == "PUT":
            r = await client.put(f"{API_URL}{path}", json=body)
        elif method == "DELETE":
            r = await client.delete(f"{API_URL}{path}")
        else:
            raise ValueError(f"Unsupported method: {method}")
        return r.json()


# ── Patient Tools ───────────────────────────────────────────────────────

@mcp.tool()
async def register_patient(
    first_name: str,
    last_name: str,
    date_of_birth: str,
    gender: str,
    phone: str,
    email: str,
    blood_type: str = "O+",
    conditions: list[str] | None = None,
    allergies: list[str] | None = None,
    primary_doctor_id: str | None = None,
    insurance_id: str | None = None,
) -> str:
    """Register a new patient with full onboarding workflow.

    Triggers: doctor notification (Gmail), Slack #intake announcement,
    insurance verification, first appointment (Google Calendar).

    Args:
        first_name: Patient's first name
        last_name: Patient's last name
        date_of_birth: Date of birth (YYYY-MM-DD)
        gender: male/female/other
        phone: Phone number
        email: Email address
        blood_type: Blood type (A+, A-, B+, B-, AB+, AB-, O+, O-)
        conditions: List of medical conditions
        allergies: List of allergies
        primary_doctor_id: UUID of assigned doctor
        insurance_id: UUID of insurance provider
    """
    result = await _api("POST", "/api/patients", {
        "first_name": first_name, "last_name": last_name,
        "date_of_birth": date_of_birth, "gender": gender,
        "phone": phone, "email": email,
        "blood_type": blood_type,
        "conditions": conditions or [],
        "allergies": allergies or [],
        "primary_doctor_id": primary_doctor_id,
        "insurance_id": insurance_id,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
async def lookup_patient(mrn: str | None = None, patient_id: str | None = None) -> str:
    """Look up a patient by MRN or patient ID.

    Args:
        mrn: Medical Record Number (e.g., MRN-00001)
        patient_id: Patient UUID
    """
    if mrn:
        result = await _api("GET", f"/api/patients/mrn/{mrn}")
    elif patient_id:
        result = await _api("GET", f"/api/patients/{patient_id}")
    else:
        result = {"error": "Provide either mrn or patient_id"}
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_patients(status: str | None = None, limit: int = 20) -> str:
    """List patients, optionally filtered by status.

    Args:
        status: Filter by status (active/discharged/admitted)
        limit: Max results (default 20)
    """
    path = f"/api/patients?limit={limit}"
    if status:
        path += f"&status={status}"
    result = await _api("GET", path)
    return json.dumps(result, indent=2)


# ── Prescription Tools ──────────────────────────────────────────────────

@mcp.tool()
async def prescribe_medication(
    patient_id: str,
    prescribing_doctor_id: str,
    medication_name: str,
    dosage: str,
    frequency: str = "once daily",
    quantity: int = 30,
    is_controlled: bool = False,
    schedule_class: str | None = None,
) -> str:
    """Create a prescription. Routes through ApprovalKit approval:
    - Routine medication: doctor approval (specific model)
    - Controlled substance: doctor + pharmacist (sequential model)

    Args:
        patient_id: Patient UUID
        prescribing_doctor_id: Doctor UUID
        medication_name: Name of medication
        dosage: Dosage (e.g., "500mg")
        frequency: How often (e.g., "twice daily")
        quantity: Number of units
        is_controlled: Whether it's a controlled substance
        schedule_class: DEA schedule (II, III, IV, V) if controlled
    """
    result = await _api("POST", "/api/prescriptions", {
        "patient_id": patient_id,
        "prescribing_doctor_id": prescribing_doctor_id,
        "medication_name": medication_name,
        "dosage": dosage,
        "frequency": frequency,
        "quantity": quantity,
        "is_controlled": is_controlled,
        "schedule_class": schedule_class,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
async def request_dose_change(
    prescription_id: str,
    requested_by_doctor_id: str,
    new_dosage: str,
    reason: str,
) -> str:
    """Request a medication dose change. Requires ALL approvals:
    doctor + pharmacist + CMO (all_of_n model).
    First dose change triggers scope creep detection.

    Args:
        prescription_id: Prescription UUID
        requested_by_doctor_id: Requesting doctor UUID
        new_dosage: New dosage (e.g., "1000mg")
        reason: Clinical reason for the change
    """
    result = await _api("POST", "/api/prescriptions/dose-change", {
        "prescription_id": prescription_id,
        "requested_by_doctor_id": requested_by_doctor_id,
        "new_dosage": new_dosage,
        "reason": reason,
    })
    return json.dumps(result, indent=2)


# ── Billing Tools ───────────────────────────────────────────────────────

@mcp.tool()
async def process_billing(
    patient_id: str,
    description: str,
    amount: float,
    procedure_code: str | None = None,
    insurance_covered: float = 0,
) -> str:
    """Process a billing record. Approval depends on amount:
    - <$500: auto-approve
    - $500-$9,999: finance manager approval
    - $10,000-$24,999: finance manager + hospital director (step-up)
    - $25,000+: finance + director + CMO

    Args:
        patient_id: Patient UUID
        description: Description of service
        amount: Total amount in USD
        procedure_code: CPT procedure code
        insurance_covered: Amount covered by insurance
    """
    result = await _api("POST", "/api/billing", {
        "patient_id": patient_id,
        "description": description,
        "amount": amount,
        "procedure_code": procedure_code,
        "insurance_covered": insurance_covered,
    })
    return json.dumps(result, indent=2)


# ── Referral Tools ──────────────────────────────────────────────────────

@mcp.tool()
async def create_referral(
    patient_id: str,
    referring_doctor_id: str,
    clinic_name: str,
    clinic_email: str,
    reason: str,
    data_scope: str = "summary",
) -> str:
    """Create an external clinic referral (HIPAA-compliant).
    Requires referring doctor's approval. Shares records via Google Drive.

    Args:
        patient_id: Patient UUID
        referring_doctor_id: Doctor UUID
        clinic_name: Name of receiving clinic
        clinic_email: Clinic's email
        reason: Reason for referral
        data_scope: What to share (summary/full/specific_records)
    """
    result = await _api("POST", "/api/referrals/external", {
        "patient_id": patient_id,
        "referring_doctor_id": referring_doctor_id,
        "clinic_name": clinic_name,
        "clinic_email": clinic_email,
        "reason": reason,
        "data_scope": data_scope,
    })
    return json.dumps(result, indent=2)


# ── Emergency Tools ─────────────────────────────────────────────────────

@mcp.tool()
async def emergency_access(
    patient_id: str,
    triggered_by: str,
    reason: str,
) -> str:
    """Request emergency access to patient data. Uses any_one approval
    with 2-minute timeout. No blackout window restrictions.

    Args:
        patient_id: Patient UUID
        triggered_by: Who is requesting (e.g., paramedic email)
        reason: Why emergency access is needed
    """
    result = await _api("POST", "/api/emergency/data-access", {
        "patient_id": patient_id,
        "triggered_by": triggered_by,
        "reason": reason,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
async def report_breach(
    triggered_by: str,
    reason: str,
    patient_id: str | None = None,
    severity: str = "critical",
) -> str:
    """Report a security breach. Auto-freezes affected accounts.
    Requires security officer + CMO approval (all_of_n).

    Args:
        triggered_by: Who detected the breach
        reason: Description of the breach
        patient_id: Affected patient UUID (optional)
        severity: Severity level (critical/high/medium)
    """
    result = await _api("POST", "/api/emergency/security-breach", {
        "patient_id": patient_id,
        "triggered_by": triggered_by,
        "reason": reason,
        "severity": severity,
    })
    return json.dumps(result, indent=2)


# ── Dashboard Tools ─────────────────────────────────────────────────────

@mcp.tool()
async def check_approval_status() -> str:
    """List all pending approval items across prescriptions, billing, and referrals."""
    result = await _api("GET", "/api/dashboard/approval-status")
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_dashboard_stats() -> str:
    """Get hospital dashboard statistics: patient counts, pending approvals,
    active emergencies, today's appointments, billing totals."""
    result = await _api("GET", "/api/dashboard/stats")
    return json.dumps(result, indent=2)


# ── Resources ───────────────────────────────────────────────────────────

@mcp.resource("healthcare://config")
async def get_config() -> str:
    """Healthcare Agent configuration and hospital info."""
    return json.dumps({
        "api_url": API_URL,
        "hospital": "MedCore General Hospital",
        "approval_system": "ApprovalKit",
        "features": [
            "Patient registration & onboarding",
            "Prescription management (routine + controlled)",
            "Dose change with scope creep detection",
            "HIPAA-compliant data sharing",
            "Amount-based billing step-up",
            "Emergency access (2-min timeout)",
            "Security breach auto-freeze",
            "Doctor vacation delegation",
            "Staff access management",
        ],
    }, indent=2)


@mcp.resource("healthcare://scenarios")
async def get_scenarios() -> str:
    """List of available demo scenarios."""
    result = await _api("GET", "/api/scenarios")
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
