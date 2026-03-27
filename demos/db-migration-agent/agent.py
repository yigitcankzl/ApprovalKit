"""
Demo Agent — Database Migration
================================
Simulates an AI agent that manages database migrations across
environments. Dev migrations are auto-approved. Staging requires
DBA approval. Production requires both the DBA and CTO (all_of_n).

Rule configuration:

  github-prod : deploy
    environment=dev         -> no rule (auto-approved)
    environment=staging     -> specific [dba]
    environment=production  -> all_of_n [dba, cto]

  slack-prod : send_message
    channel=#db-ops         -> any_one [dba]
    channel=#engineering    -> specific [engineering_manager]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/db-migration-agent/agent.py
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
    user_id="auth0|db_migration_agent",
    poll_interval=3,
    timeout=180,
)

# ── Simulated data ────────────────────────────────────────────────────────────

MIGRATIONS = {
    "M001_add_index": {
        "id": "M001",
        "type": "add_index",
        "table": "orders",
        "column": "customer_id",
        "description": "Add index on orders.customer_id for query performance",
        "risk": "low",
        "estimated_downtime": "0s",
    },
    "M002_alter_table": {
        "id": "M002",
        "type": "alter_table",
        "table": "users",
        "change": "ADD COLUMN mfa_enabled BOOLEAN DEFAULT FALSE",
        "description": "Add MFA column to users table for 2FA rollout",
        "risk": "medium",
        "estimated_downtime": "0s",
    },
    "M003_drop_column": {
        "id": "M003",
        "type": "drop_column",
        "table": "sessions",
        "column": "legacy_token",
        "description": "Remove deprecated legacy_token column from sessions",
        "risk": "high",
        "estimated_downtime": "~30s",
    },
}

ENVIRONMENTS = ["dev", "staging", "production"]

# ── Action definitions ────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="github-prod",
    action="deploy",
    params_fn=lambda migration_id, migration_type, environment, table, description, risk: {
        "migration_id": migration_id,
        "migration_type": migration_type,
        "environment": environment,
        "table": table,
        "description": description,
        "risk": risk,
    },
)
def run_migration(migration_id: str, migration_type: str, environment: str, table: str, description: str, risk: str) -> dict:
    """Execute a database migration. Approval escalates with environment."""
    return {
        "migration_id": migration_id,
        "environment": environment,
        "table": table,
        "applied": True,
    }


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post a migration status update to Slack."""
    return {"channel": channel, "posted": True}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Database Migration Agent Demo")
    print("="*60)

    m = MIGRATIONS["M001_add_index"]

    # ── Scenario 1: Add index on dev — auto-approved ──────────────────
    scenario("Scenario 1: Add index (dev) — auto-approved")
    try:
        result = run_migration(
            m["id"], m["type"], "dev", m["table"],
            m["description"], m["risk"],
        )
        print(f"  Migration {result['migration_id']} applied to {result['table']} ({result['environment']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    m = MIGRATIONS["M002_alter_table"]

    # ── Scenario 2: Alter table on staging — DBA approval ─────────────
    scenario("Scenario 2: Alter table (staging) — DBA approval required")
    try:
        result = run_migration(
            m["id"], m["type"], "staging", m["table"],
            m["description"], m["risk"],
        )
        print(f"  Migration {result['migration_id']} applied to {result['table']} ({result['environment']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    m = MIGRATIONS["M003_drop_column"]

    # ── Scenario 3: Drop column on production — DBA + CTO ────────────
    scenario("Scenario 3: Drop column (production) — DBA + CTO (all_of_n)")
    print(f"  Risk: {m['risk']} | Estimated downtime: {m['estimated_downtime']}")
    print("  Both DBA and CTO must approve this destructive migration.")
    try:
        result = run_migration(
            m["id"], m["type"], "production", m["table"],
            m["description"], m["risk"],
        )
        print(f"  Migration {result['migration_id']} applied to {result['table']} ({result['environment']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 4: Notify #db-ops ───────────────────────────────────
    scenario("Scenario 4: Notify #db-ops — DBA approval")
    try:
        result = notify_slack(
            "#db-ops",
            "Migration batch complete: M001 (dev, applied), M002 (staging, pending DBA), M003 (prod, pending DBA+CTO).",
        )
        print(f"  Posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    m = MIGRATIONS["M002_alter_table"]

    # ── Scenario 5: Promote alter_table to production ────────────────
    scenario("Scenario 5: Promote M002 to production — DBA + CTO")
    print("  Staging verified. Promoting alter_table to production.")
    try:
        result = run_migration(
            m["id"], m["type"], "production", m["table"],
            m["description"], m["risk"],
        )
        print(f"  Migration {result['migration_id']} applied to {result['table']} ({result['environment']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()
