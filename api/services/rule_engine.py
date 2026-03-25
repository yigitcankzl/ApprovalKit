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


def evaluate_condition(condition: dict, params: dict) -> bool:
    field = condition.get("field", "")
    op = condition.get("operator", "eq")
    expected = condition.get("value")

    actual = params.get(field)
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
    if not conditions:
        return True
    return all(evaluate_condition(c, params) for c in conditions)


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
    workspace_id, agent_user_id: str, connection: str, action: str, db: AsyncSession
) -> bool:
    result = await db.execute(
        select(ApprovalJob).where(
            ApprovalJob.workspace_id == workspace_id,
            ApprovalJob.agent_user_id == agent_user_id,
            ApprovalJob.connection == connection,
            ApprovalJob.action == action,
        ).limit(1)
    )
    return result.scalar_one_or_none() is None


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
