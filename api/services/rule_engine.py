import operator
import re
from datetime import datetime, time, timedelta
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.rule import Rule
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.constants import (
    REDIS_KEY_COOLDOWN, COOLDOWN_WINDOW_SECONDS,
    REDIS_KEY_BUDGET_DAILY, REDIS_KEY_BUDGET_WEEKLY, REDIS_KEY_BUDGET_MONTHLY,
    BUDGET_DAILY_TTL, BUDGET_WEEKLY_TTL, BUDGET_MONTHLY_TTL,
    REDIS_KEY_AGENT_RATE, AGENT_RATE_WINDOW_SECONDS,
)

OPERATORS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a,
    "starts_with": lambda a, b: str(a).startswith(str(b)),
    "ends_with": lambda a, b: str(a).endswith(str(b)),
    "regex": lambda a, b: bool(re.search(str(b), str(a))),
    "between": lambda a, b: b[0] <= a <= b[1] if isinstance(b, (list, tuple)) and len(b) == 2 else False,
}


def _resolve_field(params: dict, field: str) -> Any:
    """Resolve a possibly nested field like 'billing.country' or 'items.0.price'."""
    if "." not in field:
        return params.get(field)
    parts = field.split(".")
    current: Any = params
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def evaluate_condition(condition: dict, params: dict) -> bool:
    field = condition.get("field", "")
    op = condition.get("operator", "eq")
    expected = condition.get("value")

    # exists/not_exists don't need a value comparison
    if op == "exists":
        return _resolve_field(params, field) is not None
    if op == "not_exists":
        return _resolve_field(params, field) is None

    actual = _resolve_field(params, field)
    if actual is None:
        return False

    op_func = OPERATORS.get(op)
    if op_func is None:
        return False

    try:
        # Coerce types for numeric comparison
        if isinstance(expected, (int, float)) and isinstance(actual, str):
            actual = type(expected)(actual)
        # Coerce between values
        if op == "between" and isinstance(expected, (list, tuple)):
            if isinstance(actual, str):
                actual = float(actual)
        return op_func(actual, expected)
    except (TypeError, ValueError):
        return False


def evaluate_conditions(conditions: list[dict], params: dict) -> bool:
    """Evaluate a list of conditions with support for nested groups.

    Each item can be a plain condition ``{"field": ..., "operator": ..., "value": ...}``
    or a **group** ``{"logic": "or"|"and", "conditions": [...]}``.

    Top-level items are combined with AND (all must be true).
    Groups can use ``"logic": "or"`` for OR semantics.

    Example — amount > 1000 OR risk_level == "critical":
        [{"logic": "or", "conditions": [
            {"field": "amount", "operator": "gt", "value": 1000},
            {"field": "risk_level", "operator": "eq", "value": "critical"}
        ]}]
    """
    if not conditions:
        return True

    results = []
    for item in conditions:
        if "logic" in item:
            logic = item["logic"].lower()
            sub = item.get("conditions", [])
            if logic == "or":
                results.append(any(evaluate_condition(c, params) for c in sub))
            else:
                results.append(all(evaluate_condition(c, params) for c in sub))
        else:
            results.append(evaluate_condition(item, params))
    return all(results)


def is_in_blackout(rule: Rule) -> bool:
    if not rule.blackout_start or not rule.blackout_end:
        return False
    now = datetime.utcnow().time()
    start = rule.blackout_start
    end = rule.blackout_end

    if start <= end:
        return start <= now <= end
    else:
        return now >= start or now <= end


def check_time_window(rule: Rule) -> dict:
    """Check if current time is within the rule's allowed approval window.

    Uses blackout_start/blackout_end as "approval window" if present.
    Returns {"in_window": bool, "blackout": bool, "next_open": str|None}.

    If the rule has no window configured, always returns in_window=True.
    """
    if not rule.blackout_start or not rule.blackout_end:
        return {"in_window": True, "blackout": False, "next_open": None}

    now = datetime.utcnow().time()
    in_blackout = is_in_blackout(rule)

    next_open = None
    if in_blackout:
        next_open = rule.blackout_end.strftime("%H:%M UTC")

    return {"in_window": not in_blackout, "blackout": in_blackout, "next_open": next_open}


async def check_cooldown(rule: Rule, redis_client: aioredis.Redis) -> bool:
    if not rule.cooldown_max:
        return True
    key = REDIS_KEY_COOLDOWN.format(rule_id=rule.id)
    count = await redis_client.get(key)
    if count and int(count) >= rule.cooldown_max:
        return False
    return True


async def increment_cooldown(rule: Rule, redis_client: aioredis.Redis):
    if not rule.cooldown_max:
        return
    key = REDIS_KEY_COOLDOWN.format(rule_id=rule.id)
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, COOLDOWN_WINDOW_SECONDS)
    await pipe.execute()


async def check_pre_approval(rule: Rule, params: dict, redis_client: aioredis.Redis) -> bool:
    if not rule.pre_approval:
        return False
    pre = rule.pre_approval
    expires = pre.get("expires_at")
    if expires:
        exp_time = datetime.fromisoformat(expires)
        if datetime.utcnow() > exp_time:
            return False
    conditions = pre.get("conditions", [])
    return evaluate_conditions(conditions, params)


async def check_scope_creep(
    workspace_id, agent_user_id: str, connection: str, action: str, db: AsyncSession,
    params: dict | None = None,
) -> dict:
    """
    Returns {"is_new_action": bool, "amount_anomaly": bool, "anomaly_detail": str | None}.
    - is_new_action: True if agent has never requested this (connection, action) before
    - amount_anomaly: True if current amount is >3x the historical average
    """
    result = await db.execute(
        select(ApprovalJob).where(
            ApprovalJob.workspace_id == workspace_id,
            ApprovalJob.agent_user_id == agent_user_id,
            ApprovalJob.connection == connection,
            ApprovalJob.action == action,
        ).order_by(ApprovalJob.created_at.desc()).limit(100)
    )
    past_jobs = result.scalars().all()

    is_new = len(past_jobs) == 0
    amount_anomaly = False
    anomaly_detail = None
    current_amount = None
    past_amounts = []

    # Check amount anomaly if params contain a numeric amount
    if params and past_jobs:
        for key in ("amount", "amount_usd", "total"):
            raw = params.get(key)
            if raw is not None:
                try:
                    current_amount = float(raw)
                except (TypeError, ValueError):
                    pass
                break

        if current_amount is not None and current_amount > 0:
            past_amounts = []
            for job in past_jobs:
                if job.params:
                    for key in ("amount", "amount_usd", "total"):
                        raw = job.params.get(key)
                        if raw is not None:
                            try:
                                past_amounts.append(float(raw))
                            except (TypeError, ValueError):
                                pass
                            break
            if past_amounts:
                avg = sum(past_amounts) / len(past_amounts)
                if avg > 0 and current_amount > avg * 3:
                    amount_anomaly = True
                    anomaly_detail = f"Amount ${current_amount:.0f} is {current_amount/avg:.1f}x the historical avg ${avg:.0f}"

    # Statistical anomaly detection (z-score based, more robust than simple multiplier)
    z_score_anomaly = False
    z_score_detail = None
    if current_amount is not None and past_amounts and len(past_amounts) >= 5:
        import math
        avg = sum(past_amounts) / len(past_amounts)
        variance = sum((x - avg) ** 2 for x in past_amounts) / len(past_amounts)
        std_dev = math.sqrt(variance) if variance > 0 else 0
        if std_dev > 0:
            z_score = (current_amount - avg) / std_dev
            if z_score > 2.5:
                z_score_anomaly = True
                z_score_detail = f"Z-score {z_score:.1f} (amount ${current_amount:,.0f} vs avg ${avg:,.0f} ± ${std_dev:,.0f})"

    return {
        "is_new_action": is_new,
        "amount_anomaly": amount_anomaly,
        "anomaly_detail": anomaly_detail,
        "z_score_anomaly": z_score_anomaly,
        "z_score_detail": z_score_detail,
    }


async def find_matching_rule(
    workspace_id, connection: str, action: str, params: dict, db: AsyncSession
) -> Rule | None:
    result = await db.execute(
        select(Rule).where(
            Rule.workspace_id == workspace_id,
            Rule.connection == connection,
            Rule.action == action,
            Rule.is_active.is_(True),
        ).order_by(Rule.priority.desc())
    )
    rules = result.scalars().all()

    for rule in rules:
        if evaluate_conditions(rule.conditions or [], params):
            return rule

    return None


def get_required_approval_count(rule: Rule) -> int:
    if rule.model == "any_one":
        return 1
    elif rule.model == "specific":
        return 1
    elif rule.model == "all_of_n":
        return len(rule.rule_approvers)
    elif rule.model == "k_of_n":
        return rule.k_value or 1
    elif rule.model == "sequential":
        return len(rule.rule_approvers)
    return 1


def compute_risk_score(
    params: dict,
    scope_creep: dict | None = None,
    rule: Rule | None = None,
) -> dict:
    """Compute a risk score (0-100) and classification for a request.

    Factors:
    - Amount (higher = riskier)
    - Scope creep signals (new action, amount anomaly)
    - Approval model complexity (sequential > all_of_n > k_of_n > any_one)
    - Step-up presence (adds risk if step-up conditions exist)

    Returns {"score": int, "level": "low"|"medium"|"high"|"critical", "factors": [...]}.
    """
    score = 0
    factors: list[str] = []

    # Factor 1: Amount-based risk
    amount = None
    for key in ("amount", "amount_usd", "total", "price"):
        raw = _resolve_field(params, key) if params else None
        if raw is not None:
            try:
                amount = float(raw)
            except (TypeError, ValueError):
                pass
            break

    if amount is not None:
        if amount >= 10000:
            score += 40
            factors.append(f"high_amount: ${amount:,.0f}")
        elif amount >= 5000:
            score += 30
            factors.append(f"elevated_amount: ${amount:,.0f}")
        elif amount >= 1000:
            score += 20
            factors.append(f"moderate_amount: ${amount:,.0f}")
        elif amount >= 100:
            score += 10
            factors.append(f"standard_amount: ${amount:,.0f}")

    # Factor 2: Scope creep signals
    if scope_creep:
        if scope_creep.get("is_new_action"):
            score += 20
            factors.append("new_action_type")
        if scope_creep.get("amount_anomaly"):
            score += 25
            factors.append("amount_anomaly")

    # Factor 3: Approval model complexity
    if rule:
        model = str(rule.model).lower() if rule.model else ""
        model_risk = {
            "sequential": 15, "all_of_n": 12, "k_of_n": 10,
            "specific": 5, "any_one": 3,
        }
        bonus = model_risk.get(model, 0)
        if bonus:
            score += bonus
            factors.append(f"approval_model: {model}")
        if rule.step_up_conditions:
            score += 10
            factors.append("step_up_eligible")

    score = min(score, 100)

    if score >= 75:
        level = "critical"
    elif score >= 50:
        level = "high"
    elif score >= 25:
        level = "medium"
    else:
        level = "low"

    return {"score": score, "level": level, "factors": factors}


async def check_budget(
    agent_id: str, amount: float, limits: dict, redis_client: aioredis.Redis,
) -> dict:
    """Check agent spending against daily/weekly/monthly budget limits.

    ``limits`` is a dict like {"daily": 5000, "weekly": 20000, "monthly": 50000}.
    Returns {"allowed": bool, "exceeded": str|None, "spent": {"daily": ..., ...}}.
    """
    periods = {
        "daily": (REDIS_KEY_BUDGET_DAILY.format(agent_id=agent_id), BUDGET_DAILY_TTL),
        "weekly": (REDIS_KEY_BUDGET_WEEKLY.format(agent_id=agent_id), BUDGET_WEEKLY_TTL),
        "monthly": (REDIS_KEY_BUDGET_MONTHLY.format(agent_id=agent_id), BUDGET_MONTHLY_TTL),
    }

    spent: dict[str, float] = {}
    for period, (key, _ttl) in periods.items():
        raw = await redis_client.get(key)
        spent[period] = float(raw) if raw else 0.0

    for period in ("daily", "weekly", "monthly"):
        limit = limits.get(period)
        if limit is not None and (spent[period] + amount) > limit:
            return {"allowed": False, "exceeded": period, "spent": spent}

    return {"allowed": True, "exceeded": None, "spent": spent}


async def record_spending(
    agent_id: str, amount: float, redis_client: aioredis.Redis,
):
    """Increment spending counters after a successful charge."""
    periods = {
        "daily": (REDIS_KEY_BUDGET_DAILY.format(agent_id=agent_id), BUDGET_DAILY_TTL),
        "weekly": (REDIS_KEY_BUDGET_WEEKLY.format(agent_id=agent_id), BUDGET_WEEKLY_TTL),
        "monthly": (REDIS_KEY_BUDGET_MONTHLY.format(agent_id=agent_id), BUDGET_MONTHLY_TTL),
    }
    pipe = redis_client.pipeline()
    for _period, (key, ttl) in periods.items():
        pipe.incrbyfloat(key, amount)
        pipe.expire(key, ttl)
    await pipe.execute()


def build_escalation_chain(rule: Rule) -> list[dict]:
    """Build an SLA-based escalation chain from rule configuration.

    Uses rule_approvers ordered by `order` field.  Each tier has an SLA
    (timeout before escalating to the next tier).  The chain is derived
    from the rule's timeout_seconds divided equally among tiers, or
    custom SLA values from step_up_conditions if present.

    Returns a list of dicts:
    [
        {"tier": 1, "approver_id": "...", "sla_seconds": 1800, "role": "manager"},
        {"tier": 2, "approver_id": "...", "sla_seconds": 3600, "role": "director"},
        {"tier": 3, "approver_id": "...", "sla_seconds": 3600, "role": "vp"},
    ]
    """
    approvers = sorted(rule.rule_approvers, key=lambda ra: ra.order)
    if not approvers:
        return []

    # Check for custom SLA chain in step_up_conditions
    custom_chain = None
    if rule.step_up_conditions and isinstance(rule.step_up_conditions, list):
        for item in rule.step_up_conditions:
            if isinstance(item, dict) and item.get("type") == "escalation_chain":
                custom_chain = item.get("chain", [])
                break

    chain: list[dict] = []
    total_timeout = rule.timeout_seconds or 300

    for i, ra in enumerate(approvers):
        tier = i + 1
        if custom_chain and i < len(custom_chain):
            sla = custom_chain[i].get("sla_seconds", total_timeout // len(approvers))
            role = custom_chain[i].get("role", f"tier_{tier}")
        else:
            sla = total_timeout // len(approvers)
            role = f"tier_{tier}"

        chain.append({
            "tier": tier,
            "approver_id": str(ra.approver_id),
            "sla_seconds": sla,
            "role": role,
        })

    # Final tier gets escalate_to if configured
    if rule.escalate_to and chain:
        chain.append({
            "tier": len(chain) + 1,
            "approver_id": str(rule.escalate_to),
            "sla_seconds": total_timeout,
            "role": "final_escalation",
        })

    return chain



def render_binding_message(template: str | None, params: dict) -> str:
    if not template:
        # Generate a readable default message
        amt = params.get("amount_usd") or params.get("amount")
        if amt:
            return f"Approve ${amt} action?"
        return f"Approve action?"
    result = template
    for key, value in params.items():
        # Sanitize value to prevent prompt injection in binding messages
        safe_value = str(value)[:200].replace("\n", " ").replace("\r", "")
        # Support both {key} and {{key}} placeholder formats
        result = result.replace(f"{{{{{key}}}}}", safe_value)
        result = result.replace(f"{{{key}}}", safe_value)
    return result


async def check_agent_rate_limit(
    agent_id: str, connection: str, max_per_hour: int, redis_client: aioredis.Redis,
) -> dict:
    """Check if agent has exceeded the per-hour request limit for a connection.

    Uses a simple Redis counter with hourly TTL.
    Returns {"allowed": bool, "current": int, "limit": int}.
    """
    if not max_per_hour or max_per_hour <= 0:
        return {"allowed": True, "current": 0, "limit": 0}

    key = REDIS_KEY_AGENT_RATE.format(agent_id=agent_id, connection=connection)
    current = await redis_client.get(key)
    count = int(current) if current else 0

    return {
        "allowed": count < max_per_hour,
        "current": count,
        "limit": max_per_hour,
    }


async def increment_agent_rate(
    agent_id: str, connection: str, redis_client: aioredis.Redis,
):
    """Increment agent request counter for rate limiting."""
    key = REDIS_KEY_AGENT_RATE.format(agent_id=agent_id, connection=connection)
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, AGENT_RATE_WINDOW_SECONDS)
    await pipe.execute()


def check_approval_expiry(approved_at: datetime, expiry_seconds: int | None) -> dict:
    """Check if an approved decision has expired (not executed in time).

    Returns {"valid": bool, "expired_at": str | None, "remaining_seconds": int}.
    """
    if not expiry_seconds or expiry_seconds <= 0:
        return {"valid": True, "expired_at": None, "remaining_seconds": -1}

    deadline = approved_at + timedelta(seconds=expiry_seconds)
    now = datetime.utcnow()

    if now > deadline:
        return {
            "valid": False,
            "expired_at": deadline.isoformat(),
            "remaining_seconds": 0,
        }

    remaining = int((deadline - now).total_seconds())
    return {
        "valid": True,
        "expired_at": deadline.isoformat(),
        "remaining_seconds": remaining,
    }


# ---------------------------------------------------------------------------
# Rule Templates — pre-built rule configurations for common scenarios
# ---------------------------------------------------------------------------

RULE_TEMPLATES = [
    {
        "id": "high_value_payment",
        "name": "High-Value Payment Guard",
        "description": "Require manager + CFO approval for payments over $5,000. Auto-escalate on timeout.",
        "category": "finance",
        "connection": "stripe-prod",
        "action": "charge",
        "conditions": [{"field": "amount", "operator": "gte", "value": 5000}],
        "model": "sequential",
        "timeout_seconds": 1800,
        "on_timeout": "escalate",
        "step_up_model": "all_of_n",
        "step_up_conditions": [{"field": "amount", "operator": "gte", "value": 10000}],
        "max_requests_per_hour": 20,
        "approval_expiry_seconds": 1800,
        "context_template": "💳 Charge ${{amount}} to {{customer}} via Stripe",
        "approval_checklist": [
            {"id": "amount_verified", "label": "I verified the charge amount is correct"},
            {"id": "customer_verified", "label": "I confirmed the customer identity"},
        ],
    },
    {
        "id": "production_deploy",
        "name": "Production Deployment Gate",
        "description": "Require team lead approval for production deployments. Block during off-hours.",
        "category": "devops",
        "connection": "github-main",
        "action": "deploy",
        "conditions": [{"field": "env", "operator": "eq", "value": "production"}],
        "model": "specific",
        "timeout_seconds": 900,
        "on_timeout": "block",
        "blackout_start": "22:00",
        "blackout_end": "06:00",
        "max_requests_per_hour": 5,
        "approval_expiry_seconds": 900,
        "context_template": "🚀 Deploy {{ref}} to {{env}} via GitHub",
        "approval_checklist": [
            {"id": "tests_pass", "label": "All CI tests are passing"},
            {"id": "changelog", "label": "Changelog has been updated"},
            {"id": "rollback_plan", "label": "Rollback plan is documented"},
        ],
    },
    {
        "id": "bulk_email",
        "name": "Bulk Email Protection",
        "description": "Approve email sends with rate limiting. Step-up for 100+ recipients.",
        "category": "communication",
        "connection": "gmail-prod",
        "action": "send_email",
        "conditions": [],
        "model": "any_one",
        "timeout_seconds": 600,
        "on_timeout": "block",
        "max_requests_per_hour": 50,
        "approval_expiry_seconds": 600,
        "step_up_model": "all_of_n",
        "step_up_conditions": [{"field": "recipient_count", "operator": "gte", "value": 100}],
        "context_template": "📧 Send email '{{subject}}' to {{to}}",
        "trigger_rules": [
            {"connection": "slack-prod", "action": "send_message", "params": {"channel": "#email-audit", "text": "Email sent: {{subject}} → {{to}}"}}
        ],
    },
    {
        "id": "sensitive_data_access",
        "name": "Sensitive Data Access",
        "description": "K-of-N approval for accessing sensitive customer data. Full audit trail.",
        "category": "compliance",
        "connection": "salesforce-prod",
        "action": "export_data",
        "conditions": [{"field": "data_type", "operator": "in", "value": ["pii", "financial", "medical"]}],
        "model": "k_of_n",
        "k_value": 2,
        "timeout_seconds": 3600,
        "on_timeout": "block",
        "max_requests_per_hour": 3,
        "approval_expiry_seconds": 300,
        "context_template": "🔒 Export {{data_type}} data: {{query}}",
        "approval_checklist": [
            {"id": "business_need", "label": "There is a legitimate business need for this data"},
            {"id": "minimized", "label": "Data scope has been minimized to what is necessary"},
            {"id": "compliant", "label": "Export complies with data protection regulations"},
        ],
    },
    {
        "id": "refund_processing",
        "name": "Refund Processing",
        "description": "Auto-approve small refunds, require approval for large ones. Chain to notification.",
        "category": "finance",
        "connection": "stripe-prod",
        "action": "refund",
        "conditions": [{"field": "amount", "operator": "gt", "value": 100}],
        "model": "any_one",
        "timeout_seconds": 1200,
        "on_timeout": "block",
        "max_requests_per_hour": 30,
        "approval_expiry_seconds": 1200,
        "step_up_model": "sequential",
        "step_up_conditions": [{"field": "amount", "operator": "gte", "value": 1000}],
        "context_template": "💸 Refund ${{amount}} to {{customer}} — reason: {{reason}}",
        "trigger_rules": [
            {"connection": "gmail-prod", "action": "send_email", "params": {"to": "{{customer}}", "subject": "Your refund of ${{amount}} has been processed"}}
        ],
    },
    # ── Production-Ready Templates (from research) ──────────────────────
    {
        "id": "payout_transfer",
        "name": "Wire Transfer / Payout Guard",
        "description": "K-of-N for payouts over $1,000. All approvers for $25K+. Blocked after 8pm.",
        "category": "finance",
        "connection": "stripe-prod",
        "action": "payout",
        "conditions": [{"field": "amount", "operator": "gte", "value": 1000}],
        "model": "k_of_n",
        "timeout_seconds": 3600,
        "on_timeout": "block",
        "step_up_model": "all_of_n",
        "step_up_conditions": [{"field": "amount", "operator": "gte", "value": 25000}],
        "max_requests_per_hour": 5,
        "blackout_start": "20:00",
        "blackout_end": "08:00",
        "context_template": "Payout ${amount} to {destination}",
        "approval_checklist": [
            {"id": "recipient_verified", "label": "Recipient bank account is verified"},
            {"id": "invoice_matched", "label": "Payout matches an approved invoice"},
        ],
    },
    {
        "id": "subscription_create",
        "name": "Subscription Creation Guard",
        "description": "Approval for subscriptions over $500/interval. Step-up for $5K+.",
        "category": "finance",
        "connection": "stripe-prod",
        "action": "create_subscription",
        "conditions": [{"field": "interval_amount", "operator": "gte", "value": 500}],
        "model": "specific",
        "timeout_seconds": 900,
        "on_timeout": "block",
        "step_up_model": "sequential",
        "step_up_conditions": [{"field": "interval_amount", "operator": "gte", "value": 5000}],
        "max_requests_per_hour": 10,
        "context_template": "Subscription ${interval_amount}/{interval} for {customer}",
        "approval_checklist": [
            {"id": "pricing_verified", "label": "Pricing matches approved rate card"},
            {"id": "contract_exists", "label": "Customer has a signed contract"},
        ],
    },
    {
        "id": "invoice_creation",
        "name": "Invoice Creation Guard",
        "description": "Approval for invoices over $10,000. Catches fraudulent invoicing.",
        "category": "finance",
        "connection": "stripe-prod",
        "action": "create_invoice",
        "conditions": [{"field": "total", "operator": "gte", "value": 10000}],
        "model": "specific",
        "timeout_seconds": 1800,
        "on_timeout": "escalate",
        "max_requests_per_hour": 15,
        "context_template": "Invoice ${total} to {customer_email} - {description}",
    },
    {
        "id": "repo_admin",
        "name": "Repository Admin Action",
        "description": "K-of-2 for visibility changes, archiving, or branch protection removal.",
        "category": "devops",
        "connection": "github-main",
        "action": "update_repo_settings",
        "conditions": [{"field": "setting", "operator": "in", "value": ["visibility", "archive", "delete_branch_protection"]}],
        "model": "k_of_n",
        "timeout_seconds": 3600,
        "on_timeout": "block",
        "max_requests_per_hour": 3,
        "context_template": "Repo admin: {setting} on {repo}",
        "approval_checklist": [
            {"id": "impact_assessed", "label": "Impact on dependent services assessed"},
            {"id": "team_notified", "label": "Affected team members notified"},
        ],
    },
    {
        "id": "secret_management",
        "name": "Secret & Env Var Update",
        "description": "Specific approver for secret rotation with documentation checklist.",
        "category": "devops",
        "connection": "github-main",
        "action": "update_secret",
        "conditions": [],
        "model": "specific",
        "timeout_seconds": 600,
        "on_timeout": "block",
        "max_requests_per_hour": 10,
        "context_template": "Update secret {secret_name} in {environment}",
        "approval_checklist": [
            {"id": "rotation_documented", "label": "Secret rotation is documented"},
            {"id": "old_revoked", "label": "Old secret will be revoked after deployment"},
        ],
    },
    {
        "id": "infra_change",
        "name": "Infrastructure Change Gate",
        "description": "Sequential approval for IaC changes. All approvers if destroying resources.",
        "category": "devops",
        "connection": "terraform-cloud",
        "action": "apply",
        "conditions": [{"field": "resource_count", "operator": "gte", "value": 5}],
        "model": "sequential",
        "timeout_seconds": 3600,
        "on_timeout": "block",
        "step_up_model": "all_of_n",
        "step_up_conditions": [{"field": "destroys", "operator": "gte", "value": 1}],
        "blackout_start": "17:00",
        "blackout_end": "09:00",
        "max_requests_per_hour": 3,
        "context_template": "Terraform: +{creates} ~{updates} -{destroys} in {workspace}",
        "approval_checklist": [
            {"id": "plan_reviewed", "label": "Terraform plan output reviewed"},
            {"id": "no_data_loss", "label": "No data loss risk from destroys"},
            {"id": "rollback_ready", "label": "Rollback procedure documented"},
        ],
    },
    {
        "id": "key_rotation_emergency",
        "name": "Emergency Key Rotation",
        "description": "Fast approval for compromised key rotation. All approvers for full rotation.",
        "category": "devops",
        "connection": "github-prod",
        "action": "deploy",
        "conditions": [{"field": "type", "operator": "eq", "value": "key_rotation"}, {"field": "urgency", "operator": "eq", "value": "emergency"}],
        "model": "specific",
        "timeout_seconds": 300,
        "on_timeout": "block",
        "step_up_model": "all_of_n",
        "step_up_conditions": [{"field": "migration_name", "operator": "eq", "value": "rotate_all_keys"}],
        "context_template": "EMERGENCY key rotation: {service} - {reason}",
    },
    {
        "id": "slack_external",
        "name": "External Slack Channel Guard",
        "description": "Approval for messages to external/shared Slack channels.",
        "category": "communication",
        "connection": "slack-prod",
        "action": "send_message",
        "conditions": [{"field": "channel_type", "operator": "eq", "value": "external"}],
        "model": "any_one",
        "timeout_seconds": 600,
        "on_timeout": "block",
        "max_requests_per_hour": 20,
        "context_template": "Slack to #{channel}: {text}",
    },
    {
        "id": "sms_send",
        "name": "SMS Send Guard",
        "description": "Approval for SMS. Step-up for bulk (50+ recipients).",
        "category": "communication",
        "connection": "twilio-prod",
        "action": "send_sms",
        "conditions": [],
        "model": "any_one",
        "timeout_seconds": 300,
        "on_timeout": "block",
        "max_requests_per_hour": 100,
        "step_up_model": "k_of_n",
        "step_up_conditions": [{"field": "recipient_count", "operator": "gte", "value": 50}],
        "context_template": "SMS to {to}: {body}",
    },
    {
        "id": "calendar_event",
        "name": "Large Meeting Guard",
        "description": "Approval for calendar events with 10+ attendees.",
        "category": "communication",
        "connection": "google-calendar",
        "action": "create_event",
        "conditions": [{"field": "attendee_count", "operator": "gte", "value": 10}],
        "model": "any_one",
        "timeout_seconds": 600,
        "on_timeout": "block",
        "max_requests_per_hour": 10,
        "context_template": "Calendar: {summary} with {attendee_count} attendees",
    },
    {
        "id": "gdpr_deletion",
        "name": "GDPR Data Deletion",
        "description": "Sequential approval for right-to-erasure requests with identity verification.",
        "category": "compliance",
        "connection": "database-prod",
        "action": "delete_user_data",
        "conditions": [],
        "model": "sequential",
        "timeout_seconds": 7200,
        "on_timeout": "escalate",
        "max_requests_per_hour": 5,
        "context_template": "GDPR deletion: {data_subject} - {record_count} records",
        "approval_checklist": [
            {"id": "identity_verified", "label": "Data subject identity verified"},
            {"id": "legal_basis", "label": "Legal basis for deletion confirmed"},
            {"id": "backup_noted", "label": "Backup retention policy reviewed"},
            {"id": "downstream_notified", "label": "Downstream processors notified"},
        ],
    },
    {
        "id": "permission_elevation",
        "name": "Permission Elevation Guard",
        "description": "Sequential approval for admin role assignment with least-privilege checklist.",
        "category": "compliance",
        "connection": "auth0-prod",
        "action": "assign_role",
        "conditions": [{"field": "role", "operator": "in", "value": ["admin", "super_admin", "billing_admin"]}],
        "model": "sequential",
        "timeout_seconds": 3600,
        "on_timeout": "block",
        "max_requests_per_hour": 5,
        "context_template": "Elevate {user_email} to {role}",
        "approval_checklist": [
            {"id": "justification", "label": "Business justification documented"},
            {"id": "time_bound", "label": "Access is time-bound with expiry"},
            {"id": "least_privilege", "label": "Role follows least-privilege principle"},
        ],
    },
    {
        "id": "api_key_generation",
        "name": "API Key Generation Guard",
        "description": "Approval for API keys with write scopes.",
        "category": "compliance",
        "connection": "auth0-prod",
        "action": "create_api_key",
        "conditions": [{"field": "scope", "operator": "contains", "value": "write"}],
        "model": "specific",
        "timeout_seconds": 1800,
        "on_timeout": "block",
        "max_requests_per_hour": 5,
        "context_template": "API key: {name} with scopes [{scope}]",
        "approval_checklist": [
            {"id": "scopes_minimal", "label": "Scopes are minimal and justified"},
            {"id": "expiry_set", "label": "Key has appropriate expiry date"},
        ],
    },
    {
        "id": "cross_border_transfer",
        "name": "Cross-Border Data Transfer",
        "description": "Sequential approval for EU to non-EU data transfers (GDPR Art. 46).",
        "category": "compliance",
        "connection": "database-prod",
        "action": "export_data",
        "conditions": [{"field": "destination_region", "operator": "not_in", "value": ["EU", "EEA"]}],
        "model": "sequential",
        "timeout_seconds": 7200,
        "on_timeout": "block",
        "max_requests_per_hour": 2,
        "context_template": "Transfer {data_type} to {destination_region} - {record_count} records",
        "approval_checklist": [
            {"id": "legal_basis", "label": "Legal basis confirmed (SCCs, adequacy)"},
            {"id": "dpia_complete", "label": "Data Protection Impact Assessment completed"},
        ],
    },
    {
        "id": "discount_approval",
        "name": "Sales Discount Approval",
        "description": "Manager approval for 15%+ discounts. Sequential for 30%+.",
        "category": "finance",
        "connection": "salesforce-prod",
        "action": "apply_discount",
        "conditions": [{"field": "discount_percent", "operator": "gte", "value": 15}],
        "model": "specific",
        "timeout_seconds": 1800,
        "on_timeout": "escalate",
        "step_up_model": "sequential",
        "step_up_conditions": [{"field": "discount_percent", "operator": "gte", "value": 30}],
        "max_requests_per_hour": 20,
        "context_template": "Discount {discount_percent}% on {deal_name} (${deal_value})",
    },
    {
        "id": "bulk_data_update",
        "name": "Bulk Data Update Guard",
        "description": "K-of-N for bulk updates affecting 100+ records.",
        "category": "compliance",
        "connection": "salesforce-prod",
        "action": "bulk_update",
        "conditions": [{"field": "record_count", "operator": "gte", "value": 100}],
        "model": "k_of_n",
        "timeout_seconds": 3600,
        "on_timeout": "block",
        "max_requests_per_hour": 3,
        "context_template": "Bulk update {record_count} {object_type} records",
        "approval_checklist": [
            {"id": "backup_taken", "label": "Data backup created"},
            {"id": "sample_verified", "label": "Sample of changes spot-checked"},
        ],
    },
]
