"""
Demo Agent -- Performance Review
=================================
Simulates an AI agent that manages the performance review cycle:
distributing review forms, processing promotions, and handling
salary increases. Each action is gated via ApprovalKit.

Rule configuration (set up via dashboard or setup_rules.py):

  gmail-prod : review_form
    distribute forms       -> no rule  (auto-approved)

  gmail-prod : promotion
    any employee           -> all_of_n [hr_director, manager]

  stripe-prod : salary_increase
    any employee           -> sequential [hr_director, cfo]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/performance-review-agent/agent.py
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
    user_id="auth0|performance_review_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

EMPLOYEES = [
    {"name": "Nina Garcia", "email": "nina.g@company.com", "level": "L3", "department": "Engineering", "manager": "tech_lead", "salary": 110000},
    {"name": "Kevin Li", "email": "kevin.l@company.com", "level": "L4", "department": "Engineering", "manager": "eng_director", "salary": 145000},
    {"name": "Rachel Adams", "email": "rachel.a@company.com", "level": "L5", "department": "Product", "manager": "product_vp", "salary": 185000},
]

REVIEW_CYCLE = {
    "cycle": "2026-Q1",
    "start_date": "2026-03-15",
    "deadline": "2026-04-15",
    "form_url": "https://reviews.company.com/2026-q1",
}

PROMOTION_TRACKS = {
    "L3_to_L4": {"title_from": "Engineer", "title_to": "Senior Engineer", "salary_increase_pct": 15},
    "L4_to_L5": {"title_from": "Senior Engineer", "title_to": "Staff Engineer", "salary_increase_pct": 20},
    "L5_to_L6": {"title_from": "Staff Engineer", "title_to": "Principal Engineer", "salary_increase_pct": 25},
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="gmail-prod",
    action="review_form",
    params_fn=lambda employee_name, employee_email, cycle, deadline, form_url: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "review_cycle": cycle,
        "deadline": deadline,
        "form_url": form_url,
    },
)
def distribute_review_form(employee_name: str, employee_email: str,
                           cycle: str, deadline: str, form_url: str) -> dict:
    """
    Distribute performance review form to employee.
    Auto-approved -- routine administrative task.
    """
    return {"distributed": True, "employee": employee_name, "cycle": cycle}


@kit.requires_approval(
    connection="gmail-prod",
    action="promotion",
    params_fn=lambda employee_name, employee_email, current_level, new_level, new_title, salary_increase_pct: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "current_level": current_level,
        "new_level": new_level,
        "new_title": new_title,
        "salary_increase_pct": salary_increase_pct,
    },
)
def process_promotion(employee_name: str, employee_email: str,
                      current_level: str, new_level: str,
                      new_title: str, salary_increase_pct: int) -> dict:
    """
    Process employee promotion.
    Requires both HR Director and direct manager approval (all_of_n).
    """
    return {"promoted": True, "employee": employee_name, "new_level": new_level, "new_title": new_title}


@kit.requires_approval(
    connection="stripe-prod",
    action="salary_increase",
    params_fn=lambda employee_name, employee_email, current_salary, new_salary, increase_pct, reason: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "current_salary_usd": current_salary,
        "new_salary_usd": new_salary,
        "increase_pct": increase_pct,
        "reason": reason,
    },
)
def process_salary_increase(employee_name: str, employee_email: str,
                            current_salary: int, new_salary: int,
                            increase_pct: int, reason: str) -> dict:
    """
    Process salary increase in payroll.
    Sequential approval: HR Director first, then CFO.
    """
    return {"processed": True, "employee": employee_name, "new_salary": new_salary}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Performance Review Agent Demo")
    print("="*60)

    # Scenario 1: Distribute review forms -- auto-approved
    scenario("Scenario 1: Distribute review forms -- auto-approved")
    for emp in EMPLOYEES:
        try:
            result = distribute_review_form(
                emp["name"], emp["email"],
                REVIEW_CYCLE["cycle"], REVIEW_CYCLE["deadline"],
                REVIEW_CYCLE["form_url"],
            )
            print(f"  Form sent to {result['employee']} ({result['cycle']})")
        except ApprovalDenied as e:
            print(f"  Denied for {emp['name']}: {e.status}")

    time.sleep(1)

    # Scenario 2: Promotion -- HR Director + manager (all_of_n)
    scenario("Scenario 2: Promotion L3->L4 -- HR Director + manager required")
    emp = EMPLOYEES[0]
    track = PROMOTION_TRACKS["L3_to_L4"]
    print("  Both HR Director and manager must approve.")
    try:
        result = process_promotion(
            emp["name"], emp["email"],
            emp["level"], "L4",
            track["title_to"], track["salary_increase_pct"],
        )
        print(f"  Promoted: {result['employee']} -> {result['new_title']} ({result['new_level']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Salary increase -- sequential (HR Director -> CFO)
    scenario("Scenario 3: Salary increase -- sequential (HR Director -> CFO)")
    emp = EMPLOYEES[1]
    track = PROMOTION_TRACKS["L4_to_L5"]
    new_salary = int(emp["salary"] * (1 + track["salary_increase_pct"] / 100))
    print("  HR Director approves first, then CFO.")
    try:
        result = process_salary_increase(
            emp["name"], emp["email"],
            emp["salary"], new_salary,
            track["salary_increase_pct"],
            "Promotion from L4 to L5 Staff Engineer",
        )
        print(f"  Salary updated: {result['employee']}, ${result['new_salary']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
