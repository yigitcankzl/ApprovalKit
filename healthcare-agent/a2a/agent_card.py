"""
A2A Agent Card — /.well-known/agent.json
Describes the Healthcare AI Agent's capabilities for other A2A agents.
"""

AGENT_CARD = {
    "name": "Healthcare AI Agent",
    "description": (
        "HIPAA-compliant hospital management agent with human-in-the-loop approval workflows. "
        "Manages patients, prescriptions, billing, referrals, emergencies, and staff scheduling. "
        "All sensitive actions gated through ApprovalKit with multi-tier approval models."
    ),
    "url": "http://localhost:3002",
    "version": "1.0.0",
    "provider": {
        "organization": "MedCore General Hospital",
        "url": "https://medcore-hospital.com",
    },
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": True,
    },
    "skills": [
        {
            "id": "register-patient",
            "name": "Register Patient",
            "description": "Create a new patient record with full onboarding (doctor notification, Slack announcement, insurance verification, first appointment)",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "prescribe-medication",
            "name": "Prescribe Medication",
            "description": "Create and approve a prescription. Routine meds need doctor approval (specific). Controlled substances need doctor + pharmacist (sequential).",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "dose-change",
            "name": "Request Dose Change",
            "description": "Modify medication dosage. Requires doctor + pharmacist + CMO approval (all_of_n). First changes trigger scope creep detection.",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "external-referral",
            "name": "External Clinic Referral",
            "description": "Refer patient to external clinic with HIPAA-compliant record sharing via Google Drive.",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "insurance-data",
            "name": "Insurance Data Request",
            "description": "Share patient data with insurance. Supports partial approval (scope narrowing from full to summary).",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "process-billing",
            "name": "Process Billing",
            "description": "Create and approve billing records. Auto-approve <$500, step-up escalation for $10k+ and $25k+.",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "emergency-access",
            "name": "Emergency Data Access",
            "description": "Request urgent patient data access with 2-minute timeout. No blackout window. any_one approval model.",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "security-breach",
            "name": "Report Security Breach",
            "description": "Trigger security breach protocol: auto-freeze, security + CMO approval required.",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "delegate-doctor",
            "name": "Doctor Delegation",
            "description": "Set vacation delegation for a doctor. Updates shifts, notifies patients, transfers approval authority.",
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        },
        {
            "id": "lookup-patient",
            "name": "Lookup Patient",
            "description": "Search for a patient by MRN or name.",
            "inputModes": ["text/plain", "application/json"],
            "outputModes": ["application/json"],
        },
    ],
    "defaultInputModes": ["application/json"],
    "defaultOutputModes": ["application/json"],
    "authentication": {
        "schemes": ["bearer"],
    },
}
