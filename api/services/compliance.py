"""EU AI Act compliance labeling for AI agent actions.

Classifies actions into risk tiers per EU AI Act Article 6 guidelines.
Generates compliance labels that can be attached to approval jobs for
audit and regulatory reporting.

Risk Tiers (EU AI Act):
- UNACCEPTABLE: Banned practices (social scoring, real-time biometric mass surveillance)
- HIGH: Requires conformity assessment (critical infrastructure, employment, credit)
- LIMITED: Transparency obligations (chatbots, emotion recognition, deepfakes)
- MINIMAL: No obligations (spam filters, AI-enabled games)
"""

from datetime import datetime
from typing import Any


class RiskTier:
    UNACCEPTABLE = "unacceptable"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


# Action patterns mapped to risk tiers
_ACTION_RISK_MAP: dict[str, str] = {
    # HIGH risk
    "credit_score": RiskTier.HIGH,
    "credit_check": RiskTier.HIGH,
    "loan_decision": RiskTier.HIGH,
    "employment_screen": RiskTier.HIGH,
    "hiring_decision": RiskTier.HIGH,
    "terminate_employee": RiskTier.HIGH,
    "medical_diagnosis": RiskTier.HIGH,
    "insurance_pricing": RiskTier.HIGH,
    "law_enforcement": RiskTier.HIGH,
    "border_control": RiskTier.HIGH,
    "critical_infrastructure": RiskTier.HIGH,
    "deploy": RiskTier.HIGH,
    "rollback": RiskTier.HIGH,

    # LIMITED risk
    "send_email": RiskTier.LIMITED,
    "send_message": RiskTier.LIMITED,
    "chatbot_response": RiskTier.LIMITED,
    "generate_content": RiskTier.LIMITED,

    # MINIMAL risk
    "read": RiskTier.MINIMAL,
    "list": RiskTier.MINIMAL,
    "search": RiskTier.MINIMAL,
}

# Connection patterns that elevate risk
_CONNECTION_RISK_ELEVATORS: dict[str, str] = {
    "payroll": RiskTier.HIGH,
    "hr-system": RiskTier.HIGH,
    "ehr-system": RiskTier.HIGH,
    "credit-bureau": RiskTier.HIGH,
}


def classify_action(
    connection: str,
    action: str,
    params: dict | None = None,
) -> dict:
    """Classify an AI agent action per EU AI Act risk tiers.

    Returns:
    {
        "risk_tier": "minimal"|"limited"|"high"|"unacceptable",
        "requires_human_oversight": bool,
        "requires_conformity_assessment": bool,
        "transparency_obligation": bool,
        "labels": ["EU_AI_ACT_HIGH_RISK", ...],
        "article_references": ["Article 6", ...],
        "reason": str,
    }
    """
    # Base classification from action
    tier = _ACTION_RISK_MAP.get(action.lower(), RiskTier.MINIMAL)

    # Elevate if connection is in high-risk category
    conn_tier = _CONNECTION_RISK_ELEVATORS.get(connection.lower())
    if conn_tier == RiskTier.HIGH and tier in (RiskTier.MINIMAL, RiskTier.LIMITED):
        tier = RiskTier.HIGH

    # Amount-based elevation
    if params:
        for key in ("amount", "amount_usd", "total"):
            raw = params.get(key)
            if raw is not None:
                try:
                    amount = float(raw)
                    if amount >= 50000 and tier != RiskTier.UNACCEPTABLE:
                        tier = RiskTier.HIGH
                except (TypeError, ValueError):
                    pass
                break

    # Build compliance label
    labels: list[str] = []
    articles: list[str] = []
    reason = ""

    if tier == RiskTier.UNACCEPTABLE:
        labels = ["EU_AI_ACT_BANNED", "REQUIRES_IMMEDIATE_REVIEW"]
        articles = ["Article 5"]
        reason = "Action classified as unacceptable risk under EU AI Act"
    elif tier == RiskTier.HIGH:
        labels = ["EU_AI_ACT_HIGH_RISK", "HUMAN_OVERSIGHT_REQUIRED", "CONFORMITY_ASSESSMENT"]
        articles = ["Article 6", "Article 9", "Article 14"]
        reason = "High-risk AI system — requires human oversight and conformity assessment"
    elif tier == RiskTier.LIMITED:
        labels = ["EU_AI_ACT_LIMITED_RISK", "TRANSPARENCY_REQUIRED"]
        articles = ["Article 52"]
        reason = "Limited risk — transparency obligations apply"
    else:
        labels = ["EU_AI_ACT_MINIMAL_RISK"]
        articles = []
        reason = "Minimal risk — no specific obligations"

    return {
        "risk_tier": tier,
        "requires_human_oversight": tier in (RiskTier.HIGH, RiskTier.UNACCEPTABLE),
        "requires_conformity_assessment": tier == RiskTier.HIGH,
        "transparency_obligation": tier in (RiskTier.LIMITED, RiskTier.HIGH),
        "labels": labels,
        "article_references": articles,
        "reason": reason,
        "classified_at": datetime.utcnow().isoformat(),
    }
