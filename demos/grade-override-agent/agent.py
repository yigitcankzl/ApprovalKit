"""
Demo Agent — Grade Override (Education)
=======================================
Simulates an AI academic agent that handles grade corrections and
appeals. Each override tier is gated behind an ApprovalKit rule.

Rule configuration:

  sis-prod : grade_override
    type=admin_error   -> no rule  (auto-approved)
    type=grade_appeal  -> any_one  [teacher]
    type=final_override-> all_of_n [teacher, department_head]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/grade-override-agent/agent.py
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
    user_id="auth0|grade_override_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

STUDENTS = {
    "STU-1001": {"name": "Alice Chen", "course": "CS-201", "current_grade": "B+", "semester": "Fall 2025"},
    "STU-1002": {"name": "Bob Martinez", "course": "MATH-301", "current_grade": "C", "semester": "Fall 2025"},
    "STU-1003": {"name": "Carol Williams", "course": "ENG-101", "current_grade": "D", "semester": "Fall 2025"},
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="sis-prod",
    action="grade_override",
    params_fn=lambda student_id, new_grade, reason: {
        "student_id": student_id,
        "student_name": STUDENTS[student_id]["name"],
        "course": STUDENTS[student_id]["course"],
        "old_grade": STUDENTS[student_id]["current_grade"],
        "new_grade": new_grade,
        "type": "admin_error",
        "reason": reason,
    },
)
def fix_admin_error(student_id: str, new_grade: str, reason: str) -> dict:
    """
    Correct an administrative data-entry error.
    Auto-approved -- no human review needed.
    """
    student = STUDENTS[student_id]
    return {
        "student": student["name"],
        "course": student["course"],
        "old_grade": student["current_grade"],
        "new_grade": new_grade,
    }


@kit.requires_approval(
    connection="sis-prod",
    action="grade_override",
    params_fn=lambda student_id, new_grade, justification: {
        "student_id": student_id,
        "student_name": STUDENTS[student_id]["name"],
        "course": STUDENTS[student_id]["course"],
        "old_grade": STUDENTS[student_id]["current_grade"],
        "new_grade": new_grade,
        "type": "grade_appeal",
        "justification": justification,
    },
)
def process_grade_appeal(student_id: str, new_grade: str, justification: str) -> dict:
    """
    Process a student grade appeal.
    Requires teacher approval.
    """
    student = STUDENTS[student_id]
    return {
        "student": student["name"],
        "course": student["course"],
        "old_grade": student["current_grade"],
        "new_grade": new_grade,
        "status": "appeal_approved",
    }


@kit.requires_approval(
    connection="sis-prod",
    action="grade_override",
    params_fn=lambda student_id, new_grade, justification: {
        "student_id": student_id,
        "student_name": STUDENTS[student_id]["name"],
        "course": STUDENTS[student_id]["course"],
        "old_grade": STUDENTS[student_id]["current_grade"],
        "new_grade": new_grade,
        "type": "final_override",
        "justification": justification,
    },
)
def final_grade_override(student_id: str, new_grade: str, justification: str) -> dict:
    """
    Final grade override -- bypasses normal appeal process.
    Requires both teacher AND department_head approval (all_of_n).
    """
    student = STUDENTS[student_id]
    return {
        "student": student["name"],
        "course": student["course"],
        "old_grade": student["current_grade"],
        "new_grade": new_grade,
        "status": "final_override_applied",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Grade Override Agent Demo")
    print("="*60)

    # -- Scenario 1: Admin error -- auto-approved ---
    scenario("Scenario 1: Admin error fix -- auto-approved")
    print("  Typo in grade entry: B+ should be A-")
    try:
        result = fix_admin_error("STU-1001", "A-", "Data entry typo in grade portal")
        print(f"  Override complete: {result['student']} {result['course']}")
        print(f"  {result['old_grade']} -> {result['new_grade']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Grade appeal -- teacher approves ---
    scenario("Scenario 2: Grade appeal -- waiting for teacher")
    print("  Student appeals C grade with evidence of grading error.")
    try:
        result = process_grade_appeal(
            "STU-1002", "B",
            "Student provided exam paper showing Q4 was graded incorrectly"
        )
        print(f"  Appeal resolved: {result['student']} {result['course']}")
        print(f"  {result['old_grade']} -> {result['new_grade']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Final override -- teacher + department_head ---
    scenario("Scenario 3: Final override -- teacher + department_head required")
    print("  Both teacher and department head must approve.")
    try:
        result = final_grade_override(
            "STU-1003", "C+",
            "Dean's review found systematic grading inconsistency in section"
        )
        print(f"  Final override applied: {result['student']} {result['course']}")
        print(f"  {result['old_grade']} -> {result['new_grade']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
