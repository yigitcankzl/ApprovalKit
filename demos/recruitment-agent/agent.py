"""
Demo Agent -- Recruitment
=========================
Simulates an AI recruitment agent that schedules interviews,
generates offer letters, assembles salary packages, and processes
terminations. Every sensitive action is gated behind ApprovalKit rules.

Rule configuration (set up via dashboard or setup_rules.py):

  calendar-prod : interview_invite
    any candidate          -> no rule  (auto-approved)

  gmail-prod : offer_letter
    any candidate          -> specific [hr_director]

  gmail-prod : salary_package
    any candidate          -> sequential [hr_director, cfo]

  gmail-prod : termination
    any employee           -> all_of_n [hr_director, ceo]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/recruitment-agent/agent.py
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
    user_id="auth0|recruitment_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

CANDIDATES = [
    {"name": "Sarah Chen", "email": "sarah.chen@gmail.com", "role": "Senior Engineer", "level": "L5"},
    {"name": "James Okafor", "email": "james.o@outlook.com", "role": "Product Manager", "level": "L4"},
    {"name": "Priya Sharma", "email": "priya.s@yahoo.com", "role": "VP Engineering", "level": "L8"},
]

EMPLOYEES = [
    {"name": "Tom Wilson", "email": "tom.wilson@company.com", "department": "Engineering", "tenure_years": 3},
]

INTERVIEW_SLOTS = [
    {"date": "2026-04-02", "time": "10:00 AM", "panel": ["hiring_mgr", "tech_lead"]},
    {"date": "2026-04-03", "time": "2:00 PM", "panel": ["hiring_mgr", "hr_director"]},
]

SALARY_BANDS = {
    "L4": {"min": 120000, "mid": 145000, "max": 170000},
    "L5": {"min": 160000, "mid": 190000, "max": 220000},
    "L8": {"min": 280000, "mid": 340000, "max": 400000},
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="calendar-prod",
    action="interview_invite",
    params_fn=lambda candidate_name, candidate_email, role, date, time_slot, panel: {
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "role": role,
        "date": date,
        "time": time_slot,
        "panel": panel,
    },
)
def schedule_interview(candidate_name: str, candidate_email: str, role: str,
                       date: str, time_slot: str, panel: list) -> dict:
    """
    Schedule an interview via Google Calendar.
    Auto-approved -- low risk, informational only.
    """
    return {"scheduled": True, "candidate": candidate_name, "date": date}


@kit.requires_approval(
    connection="gmail-prod",
    action="offer_letter",
    params_fn=lambda candidate_name, candidate_email, role, level, base_salary: {
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "role": role,
        "level": level,
        "base_salary_usd": base_salary,
    },
)
def send_offer_letter(candidate_name: str, candidate_email: str, role: str,
                      level: str, base_salary: int) -> dict:
    """
    Send an offer letter via Gmail.
    Requires HR Director approval before dispatch.
    """
    return {"offer_sent": True, "candidate": candidate_name, "salary": base_salary}


@kit.requires_approval(
    connection="gmail-prod",
    action="salary_package",
    params_fn=lambda candidate_name, candidate_email, role, base_salary, equity_usd, sign_on_bonus: {
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "role": role,
        "base_salary_usd": base_salary,
        "equity_usd": equity_usd,
        "sign_on_bonus_usd": sign_on_bonus,
        "total_comp_usd": base_salary + equity_usd + sign_on_bonus,
    },
)
def assemble_salary_package(candidate_name: str, candidate_email: str, role: str,
                            base_salary: int, equity_usd: int, sign_on_bonus: int) -> dict:
    """
    Assemble and send full compensation package.
    Sequential approval: HR Director first, then CFO.
    """
    total = base_salary + equity_usd + sign_on_bonus
    return {"package_sent": True, "candidate": candidate_name, "total_comp": total}


@kit.requires_approval(
    connection="gmail-prod",
    action="termination",
    params_fn=lambda employee_name, employee_email, department, reason, severance_months: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "department": department,
        "reason": reason,
        "severance_months": severance_months,
    },
)
def process_termination(employee_name: str, employee_email: str, department: str,
                        reason: str, severance_months: int) -> dict:
    """
    Process employee termination.
    Requires both HR Director and CEO approval (all_of_n).
    """
    return {"terminated": True, "employee": employee_name, "severance_months": severance_months}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Recruitment Agent Demo")
    print("="*60)

    # Scenario 1: Schedule interview -- auto-approved
    scenario("Scenario 1: Schedule interview -- auto-approved")
    c = CANDIDATES[0]
    slot = INTERVIEW_SLOTS[0]
    try:
        result = schedule_interview(
            c["name"], c["email"], c["role"],
            slot["date"], slot["time"], slot["panel"],
        )
        print(f"  Interview scheduled for {result['candidate']} on {result['date']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Offer letter -- HR Director approval
    scenario("Scenario 2: Offer letter -- HR Director approval required")
    c = CANDIDATES[1]
    band = SALARY_BANDS[c["level"]]
    try:
        result = send_offer_letter(
            c["name"], c["email"], c["role"], c["level"], band["mid"],
        )
        print(f"  Offer sent to {result['candidate']}: ${result['salary']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: VP salary package -- HR Director then CFO (sequential)
    scenario("Scenario 3: VP salary package -- sequential (HR Director -> CFO)")
    c = CANDIDATES[2]
    band = SALARY_BANDS[c["level"]]
    print("  HR Director approves first, then CFO.")
    try:
        result = assemble_salary_package(
            c["name"], c["email"], c["role"],
            band["max"], 150000, 50000,
        )
        print(f"  Package sent to {result['candidate']}: ${result['total_comp']:,} total comp")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: Termination -- HR Director + CEO (all_of_n)
    scenario("Scenario 4: Termination -- all_of_n (HR Director + CEO)")
    emp = EMPLOYEES[0]
    print("  Both HR Director and CEO must approve.")
    try:
        result = process_termination(
            emp["name"], emp["email"], emp["department"],
            "Position eliminated in restructuring", 3,
        )
        print(f"  Termination processed: {result['employee']}, {result['severance_months']}mo severance")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
