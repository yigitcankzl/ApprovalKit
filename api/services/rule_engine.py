import operator
import re
from datetime import datetime, time
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

    actual = _resolve_field(params, field)
    if actual is None:
        return False

    op_func = OPERATORS.get(op)
    if op_func is None:
        return False

    try:
        if isinstance(expected, (int, float)) and isinstance(actual, str):
            actual = type(expected)(actual)
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
        return f"Approval requested for action with params: {params}"
    result = template
    for key, value in params.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result
