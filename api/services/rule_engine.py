import operator
import re
from datetime import datetime, time
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.rule import Rule
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.constants import REDIS_KEY_COOLDOWN, COOLDOWN_WINDOW_SECONDS

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

    # Check amount anomaly if params contain a numeric amount
    if params and past_jobs:
        current_amount = None
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

    return {"is_new_action": is_new, "amount_anomaly": amount_anomaly, "anomaly_detail": anomaly_detail}


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


def render_binding_message(template: str | None, params: dict) -> str:
    if not template:
        return f"Approval requested for action with params: {params}"
    result = template
    for key, value in params.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result
