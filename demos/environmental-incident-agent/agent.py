"""
Demo Agent — Environmental Incident (Energy)
=============================================
Simulates an AI agent that handles environmental monitoring
and incident response in the energy sector.

Rule configuration:

  env-monitoring : incident
    type=monitoring       -> no rule  (auto-approved)
    type=minor_spill      -> no rule  (auto-approved, sends notification)
    type=major_incident   -> all_of_n [CEO, environmental_officer]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/environmental-incident-agent/agent.py
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
    user_id="auth0|environmental_incident_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

SITES = {
    "SITE-A1": {"name": "North Sea Platform Alpha", "region": "North Sea", "type": "offshore_drilling"},
    "SITE-B2": {"name": "Texas Refinery Complex", "region": "Gulf Coast", "type": "refinery"},
    "SITE-C3": {"name": "Alaska Pipeline Station 7", "region": "North Slope", "type": "pipeline"},
}

INCIDENTS = {
    "INC-001": {
        "site": "SITE-A1",
        "description": "Routine air quality sensor reading",
        "severity": "info",
        "pollutant": "CO2",
        "reading_ppm": 385,
        "threshold_ppm": 500,
    },
    "INC-002": {
        "site": "SITE-B2",
        "description": "Small diesel spill during transfer (< 10 gallons)",
        "severity": "minor",
        "volume_gallons": 8,
        "substance": "diesel",
        "contained": True,
    },
    "INC-003": {
        "site": "SITE-C3",
        "description": "Pipeline rupture detected; crude oil leak",
        "severity": "major",
        "volume_gallons": 15000,
        "substance": "crude_oil",
        "contained": False,
        "estimated_cleanup_usd": 2500000,
    },
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="env-monitoring",
    action="incident",
    params_fn=lambda incident_id: {
        "incident_id": incident_id,
        "site": SITES[INCIDENTS[incident_id]["site"]]["name"],
        "region": SITES[INCIDENTS[incident_id]["site"]]["region"],
        "description": INCIDENTS[incident_id]["description"],
        "severity": INCIDENTS[incident_id]["severity"],
        "type": "monitoring",
    },
)
def log_monitoring_event(incident_id: str) -> dict:
    """
    Log a routine monitoring event.
    Auto-approved -- informational data collection.
    """
    incident = INCIDENTS[incident_id]
    site = SITES[incident["site"]]
    return {
        "incident_id": incident_id,
        "site": site["name"],
        "reading_ppm": incident.get("reading_ppm", "N/A"),
        "status": "logged",
    }


@kit.requires_approval(
    connection="env-monitoring",
    action="incident",
    params_fn=lambda incident_id: {
        "incident_id": incident_id,
        "site": SITES[INCIDENTS[incident_id]["site"]]["name"],
        "region": SITES[INCIDENTS[incident_id]["site"]]["region"],
        "description": INCIDENTS[incident_id]["description"],
        "severity": INCIDENTS[incident_id]["severity"],
        "substance": INCIDENTS[incident_id]["substance"],
        "volume_gallons": INCIDENTS[incident_id]["volume_gallons"],
        "contained": INCIDENTS[incident_id]["contained"],
        "type": "minor_spill",
        "notify": True,
    },
)
def report_minor_spill(incident_id: str) -> dict:
    """
    Report a minor spill and trigger automatic notifications.
    Auto-approved with notification to environmental team.
    """
    incident = INCIDENTS[incident_id]
    site = SITES[incident["site"]]
    return {
        "incident_id": incident_id,
        "site": site["name"],
        "substance": incident["substance"],
        "volume_gallons": incident["volume_gallons"],
        "status": "reported_and_notified",
    }


@kit.requires_approval(
    connection="env-monitoring",
    action="incident",
    params_fn=lambda incident_id, response_plan: {
        "incident_id": incident_id,
        "site": SITES[INCIDENTS[incident_id]["site"]]["name"],
        "region": SITES[INCIDENTS[incident_id]["site"]]["region"],
        "description": INCIDENTS[incident_id]["description"],
        "severity": INCIDENTS[incident_id]["severity"],
        "substance": INCIDENTS[incident_id]["substance"],
        "volume_gallons": INCIDENTS[incident_id]["volume_gallons"],
        "contained": INCIDENTS[incident_id]["contained"],
        "estimated_cleanup_usd": INCIDENTS[incident_id]["estimated_cleanup_usd"],
        "type": "major_incident",
        "response_plan": response_plan,
    },
)
def declare_major_incident(incident_id: str, response_plan: str) -> dict:
    """
    Declare a major environmental incident and activate response.
    Requires both CEO AND environmental_officer approval (all_of_n).
    """
    incident = INCIDENTS[incident_id]
    site = SITES[incident["site"]]
    return {
        "incident_id": incident_id,
        "site": site["name"],
        "substance": incident["substance"],
        "volume_gallons": incident["volume_gallons"],
        "estimated_cleanup_usd": incident["estimated_cleanup_usd"],
        "status": "major_incident_declared",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Environmental Incident Agent Demo")
    print("="*60)

    # -- Scenario 1: Monitoring -- auto-approved ---
    scenario("Scenario 1: Routine monitoring -- auto-approved")
    try:
        result = log_monitoring_event("INC-001")
        print(f"  Site: {result['site']}")
        print(f"  Reading: {result['reading_ppm']} ppm")
        print(f"  Status: {result['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Minor spill -- auto with notification ---
    scenario("Scenario 2: Minor spill (8 gal diesel) -- auto-approved + notify")
    print("  Contained spill triggers automatic notification.")
    try:
        result = report_minor_spill("INC-002")
        print(f"  Site: {result['site']}")
        print(f"  Substance: {result['substance']}, {result['volume_gallons']} gal")
        print(f"  Status: {result['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Major incident -- CEO + environmental_officer ---
    scenario("Scenario 3: Major incident (15k gal crude) -- CEO + env officer")
    print("  Both CEO and environmental_officer must approve response plan.")
    try:
        result = declare_major_incident(
            "INC-003",
            "Deploy containment booms; activate spill response team; notify EPA within 24h"
        )
        print(f"  Site: {result['site']}")
        print(f"  Substance: {result['substance']}, {result['volume_gallons']:,} gal")
        print(f"  Cleanup estimate: ${result['estimated_cleanup_usd']:,}")
        print(f"  Status: {result['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
