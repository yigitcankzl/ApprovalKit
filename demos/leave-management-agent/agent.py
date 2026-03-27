"""
Demo Agent -- Leave Management
===============================
Simulates an AI leave management agent that processes time-off
requests at various durations and urgency levels. Each tier of
leave has its own approval gate via ApprovalKit.

Rule configuration (set up via dashboard or setup_rules.py):

  calendar-prod : short_leave
    1-2 day leave          -> no rule  (auto-approved)

  calendar-prod : week_leave
    3-5 day leave          -> specific [manager]

  calendar-prod : long_leave
    6+ day leave           -> specific [hr_director]

  calendar-prod : critical_period
    leave during crunch    -> all_of_n [manager, ceo]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/leave-management-agent/agent.py
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
    user_id="auth0|leave_management_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

EMPLOYEES = [
    {"name": "Mia Thompson", "email": "mia.t@company.com", "department": "Engineering", "manager": "tech_lead"},
    {"name": "Raj Patel", "email": "raj.p@company.com", "department": "Sales", "manager": "sales_director"},
    {"name": "Lena Kim", "email": "lena.k@company.com", "department": "Product", "manager": "product_lead"},
    {"name": "Omar Hassan", "email": "omar.h@company.com", "department": "Engineering", "manager": "tech_lead"},
]

LEAVE_BALANCE = {
    "Mia Thompson": {"vacation": 18, "sick": 10, "personal": 3},
    "Raj Patel": {"vacation": 12, "sick": 10, "personal": 3},
    "Lena Kim": {"vacation": 22, "sick": 10, "personal": 3},
    "Omar Hassan": {"vacation": 5, "sick": 10, "personal": 3},
}

CRITICAL_PERIODS = [
    {"name": "Q1 Close", "start": "2026-03-25", "end": "2026-04-05"},
    {"name": "Product Launch", "start": "2026-04-15", "end": "2026-04-30"},
]

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="calendar-prod",
    action="short_leave",
    params_fn=lambda employee_name, employee_email, leave_type, start_date, days: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "leave_type": leave_type,
        "start_date": start_date,
        "duration_days": days,
    },
)
def request_short_leave(employee_name: str, employee_email: str,
                        leave_type: str, start_date: str, days: int) -> dict:
    """
    Request 1-2 day leave. Auto-approved -- minimal disruption.
    Calendar event created automatically.
    """
    return {"approved": True, "employee": employee_name, "days": days}


@kit.requires_approval(
    connection="calendar-prod",
    action="week_leave",
    params_fn=lambda employee_name, employee_email, leave_type, start_date, days, manager: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "leave_type": leave_type,
        "start_date": start_date,
        "duration_days": days,
        "approver": manager,
    },
)
def request_week_leave(employee_name: str, employee_email: str,
                       leave_type: str, start_date: str, days: int,
                       manager: str) -> dict:
    """
    Request 3-5 day leave. Requires direct manager approval.
    """
    return {"approved": True, "employee": employee_name, "days": days}


@kit.requires_approval(
    connection="calendar-prod",
    action="long_leave",
    params_fn=lambda employee_name, employee_email, leave_type, start_date, days, reason: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "leave_type": leave_type,
        "start_date": start_date,
        "duration_days": days,
        "reason": reason,
    },
)
def request_long_leave(employee_name: str, employee_email: str,
                       leave_type: str, start_date: str, days: int,
                       reason: str) -> dict:
    """
    Request 6+ day leave. Requires HR Director approval.
    Coverage plan must be submitted.
    """
    return {"approved": True, "employee": employee_name, "days": days}


@kit.requires_approval(
    connection="calendar-prod",
    action="critical_period",
    params_fn=lambda employee_name, employee_email, leave_type, start_date, days, period_name, justification: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "leave_type": leave_type,
        "start_date": start_date,
        "duration_days": days,
        "critical_period": period_name,
        "justification": justification,
    },
)
def request_critical_period_leave(employee_name: str, employee_email: str,
                                  leave_type: str, start_date: str, days: int,
                                  period_name: str, justification: str) -> dict:
    """
    Request leave during a critical business period.
    Requires both manager and CEO approval (all_of_n).
    """
    return {"approved": True, "employee": employee_name, "days": days, "period": period_name}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Leave Management Agent Demo")
    print("="*60)

    # Scenario 1: Short leave (1 day) -- auto-approved
    scenario("Scenario 1: Short leave (1 day) -- auto-approved")
    emp = EMPLOYEES[0]
    try:
        result = request_short_leave(
            emp["name"], emp["email"], "personal", "2026-04-07", 1,
        )
        print(f"  Leave approved: {result['employee']}, {result['days']} day(s)")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Week leave (5 days) -- manager approval
    scenario("Scenario 2: Week leave (5 days) -- manager approval required")
    emp = EMPLOYEES[1]
    try:
        result = request_week_leave(
            emp["name"], emp["email"], "vacation",
            "2026-05-04", 5, emp["manager"],
        )
        print(f"  Leave approved: {result['employee']}, {result['days']} day(s)")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Long leave (14 days) -- HR Director approval
    scenario("Scenario 3: Long leave (14 days) -- HR Director approval required")
    emp = EMPLOYEES[2]
    try:
        result = request_long_leave(
            emp["name"], emp["email"], "vacation",
            "2026-06-15", 14, "Extended family trip, coverage arranged with team",
        )
        print(f"  Leave approved: {result['employee']}, {result['days']} day(s)")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: Critical period leave -- manager + CEO (all_of_n)
    scenario("Scenario 4: Critical period leave -- manager + CEO required")
    emp = EMPLOYEES[3]
    period = CRITICAL_PERIODS[0]
    print("  Both manager and CEO must approve.")
    try:
        result = request_critical_period_leave(
            emp["name"], emp["email"], "personal",
            "2026-03-30", 3, period["name"],
            "Family emergency, senior dev covering sprint commitments",
        )
        print(f"  Leave approved: {result['employee']}, {result['days']} day(s) during {result['period']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
