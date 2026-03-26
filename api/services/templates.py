"""Approval rule templates (blueprints) for common industry scenarios.

Pre-built rule configurations that can be applied to a workspace with one click.
Each template includes rules, conditions, approval models, and step-up config.
"""

TEMPLATES = {
    "fintech_payments": {
        "name": "FinTech Payments",
        "description": "Tiered approval for financial transactions with step-up for high values",
        "industry": "fintech",
        "rules": [
            {
                "name": "Low-value payment (auto-approve)",
                "connection": "stripe-prod",
                "action": "charge",
                "conditions": [{"field": "amount_usd", "operator": "lt", "value": 500}],
                "model": "any_one",
                "timeout_seconds": 60,
            },
            {
                "name": "Mid-range payment (manager approval)",
                "connection": "stripe-prod",
                "action": "charge",
                "conditions": [
                    {"field": "amount_usd", "operator": "gte", "value": 500},
                    {"field": "amount_usd", "operator": "lt", "value": 5000},
                ],
                "model": "any_one",
                "timeout_seconds": 300,
            },
            {
                "name": "High-value payment (dual approval)",
                "connection": "stripe-prod",
                "action": "charge",
                "conditions": [{"field": "amount_usd", "operator": "gte", "value": 5000}],
                "model": "all_of_n",
                "timeout_seconds": 600,
                "step_up_model": "sequential",
                "step_up_conditions": [{"field": "amount_usd", "operator": "gte", "value": 10000}],
            },
        ],
    },
    "healthcare_phi": {
        "name": "Healthcare PHI Access",
        "description": "HIPAA-compliant approval for Protected Health Information access",
        "industry": "healthcare",
        "rules": [
            {
                "name": "PHI read access",
                "connection": "ehr-system",
                "action": "read_patient",
                "conditions": [],
                "model": "any_one",
                "timeout_seconds": 120,
            },
            {
                "name": "PHI export (compliance officer required)",
                "connection": "ehr-system",
                "action": "export_records",
                "conditions": [],
                "model": "all_of_n",
                "timeout_seconds": 600,
            },
            {
                "name": "PHI bulk access (dual approval + audit)",
                "connection": "ehr-system",
                "action": "bulk_query",
                "conditions": [{"field": "record_count", "operator": "gt", "value": 100}],
                "model": "sequential",
                "timeout_seconds": 900,
            },
        ],
    },
    "devops_deployment": {
        "name": "DevOps Deployment",
        "description": "Environment-based approval for CI/CD pipelines",
        "industry": "devops",
        "rules": [
            {
                "name": "Staging deploy (auto-approve)",
                "connection": "github-prod",
                "action": "deploy",
                "conditions": [{"field": "environment", "operator": "eq", "value": "staging"}],
                "model": "any_one",
                "timeout_seconds": 60,
            },
            {
                "name": "Production deploy (team lead approval)",
                "connection": "github-prod",
                "action": "deploy",
                "conditions": [{"field": "environment", "operator": "eq", "value": "production"}],
                "model": "any_one",
                "timeout_seconds": 300,
                "blackout_start": "22:00",
                "blackout_end": "06:00",
            },
            {
                "name": "Rollback (immediate, any approver)",
                "connection": "github-prod",
                "action": "rollback",
                "conditions": [],
                "model": "any_one",
                "timeout_seconds": 60,
            },
        ],
    },
    "ai_governance": {
        "name": "AI Agent Governance",
        "description": "EU AI Act aligned controls for high-risk AI agent actions",
        "industry": "ai",
        "rules": [
            {
                "name": "Low-risk AI action (auto-approve)",
                "connection": "*",
                "action": "read",
                "conditions": [{"field": "risk_level", "operator": "eq", "value": "low"}],
                "model": "any_one",
                "timeout_seconds": 60,
            },
            {
                "name": "High-risk AI action (human oversight required)",
                "connection": "*",
                "action": "*",
                "conditions": [
                    {"logic": "or", "conditions": [
                        {"field": "risk_level", "operator": "eq", "value": "high"},
                        {"field": "risk_level", "operator": "eq", "value": "critical"},
                    ]},
                ],
                "model": "all_of_n",
                "timeout_seconds": 600,
                "step_up_model": "sequential",
                "step_up_conditions": [{"field": "affects_humans", "operator": "eq", "value": True}],
            },
        ],
    },
    "ecommerce_operations": {
        "name": "E-Commerce Operations",
        "description": "Approval rules for refunds, inventory, and pricing changes",
        "industry": "ecommerce",
        "rules": [
            {
                "name": "Small refund (auto-approve)",
                "connection": "stripe-prod",
                "action": "refund",
                "conditions": [{"field": "amount_usd", "operator": "lt", "value": 100}],
                "model": "any_one",
                "timeout_seconds": 60,
            },
            {
                "name": "Large refund (manager approval)",
                "connection": "stripe-prod",
                "action": "refund",
                "conditions": [{"field": "amount_usd", "operator": "gte", "value": 100}],
                "model": "any_one",
                "timeout_seconds": 300,
            },
            {
                "name": "Price change > 20% (approval required)",
                "connection": "shopify-prod",
                "action": "update_price",
                "conditions": [{"field": "price_change_pct", "operator": "gt", "value": 20}],
                "model": "any_one",
                "timeout_seconds": 300,
            },
        ],
    },
    "hr_operations": {
        "name": "HR Operations",
        "description": "Employee onboarding, offboarding, and access management",
        "industry": "hr",
        "rules": [
            {
                "name": "New employee onboarding",
                "connection": "gmail-prod",
                "action": "send_email",
                "conditions": [{"field": "type", "operator": "eq", "value": "onboarding"}],
                "model": "any_one",
                "timeout_seconds": 300,
            },
            {
                "name": "Employee offboarding (HR + manager)",
                "connection": "github-prod",
                "action": "remove_member",
                "conditions": [],
                "model": "all_of_n",
                "timeout_seconds": 600,
            },
            {
                "name": "Salary change (sequential: HR → Finance → CEO)",
                "connection": "payroll-prod",
                "action": "update_salary",
                "conditions": [],
                "model": "sequential",
                "timeout_seconds": 900,
            },
        ],
    },
}


def list_templates() -> list[dict]:
    """Return all available templates with metadata (no rules detail)."""
    return [
        {
            "id": key,
            "name": t["name"],
            "description": t["description"],
            "industry": t["industry"],
            "rule_count": len(t["rules"]),
        }
        for key, t in TEMPLATES.items()
    ]


def get_template(template_id: str) -> dict | None:
    """Get a specific template with full rule definitions."""
    t = TEMPLATES.get(template_id)
    if not t:
        return None
    return {"id": template_id, **t}
