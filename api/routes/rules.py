import uuid
from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.rule import Rule, RuleApprover, ApprovalModel, TimeoutAction
from api.models.approver import Approver
from api.schemas.rule import RuleCreate, RuleUpdate, RuleResponse
from api.services.rule_engine import (
    evaluate_conditions, render_binding_message,
    is_in_blackout, check_time_window, compute_risk_score,
    get_required_approval_count, build_escalation_chain,
    RULE_TEMPLATES,
)
from api.middleware.fga import require_rule_read, require_rule_write, require_workspace_admin
from api.middleware.workspace import get_current_workspace
from api.models.workspace import Workspace
from api.utils import parse_time as _parse_time

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


async def _resolve_workspace_id(
    workspace: Workspace = Depends(get_current_workspace),
) -> uuid.UUID:
    return workspace.id


def _rule_to_response(rule: Rule) -> dict:
    return {
        "id": str(rule.id),
        "name": rule.name,
        "connection": rule.connection,
        "action": rule.action,
        "conditions": rule.conditions or [],
        "model": rule.model.value if isinstance(rule.model, ApprovalModel) else rule.model,
        "approver_ids": [str(ra.approver_id) for ra in rule.rule_approvers],
        "k_value": rule.k_value,
        "timeout_seconds": rule.timeout_seconds,
        "on_timeout": rule.on_timeout.value if isinstance(rule.on_timeout, TimeoutAction) else rule.on_timeout,
        "escalate_to": str(rule.escalate_to) if rule.escalate_to else None,
        "cooldown_max": rule.cooldown_max,
        "blackout_start": rule.blackout_start.isoformat() if rule.blackout_start else None,
        "blackout_end": rule.blackout_end.isoformat() if rule.blackout_end else None,
        "pre_approval": rule.pre_approval,
        "context_template": rule.context_template,
        "partial_approval": rule.partial_approval,
        "quorum_window": rule.quorum_window,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "step_up_model": rule.step_up_model.value if rule.step_up_model and isinstance(rule.step_up_model, ApprovalModel) else None,
        "step_up_conditions": rule.step_up_conditions or [],
        "approval_checklist": rule.approval_checklist,
        "max_requests_per_hour": rule.max_requests_per_hour,
        "approval_expiry_seconds": rule.approval_expiry_seconds,
        "trigger_rules": rule.trigger_rules,
        "on_approve_actions": rule.on_approve_actions,
        "risk_auto_approve_threshold": getattr(rule, "risk_auto_approve_threshold", None),
        "reauth_every_n": getattr(rule, "reauth_every_n", None),
        "budget_limits": getattr(rule, "budget_limits", None),
        "allowed_days": getattr(rule, "allowed_days", None),
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }


@router.post("", response_model=RuleResponse)
async def create_rule(
    data: RuleCreate,
    db: AsyncSession = Depends(get_db),
    ws_id: uuid.UUID = Depends(_resolve_workspace_id),
    _fga: None = Depends(require_workspace_admin),
):
    rule = Rule(
        workspace_id=ws_id,
        name=data.name,
        connection=data.connection,
        action=data.action,
        conditions=[c.model_dump() for c in data.conditions],
        model=data.model,
        k_value=data.k_value,
        timeout_seconds=data.timeout_seconds,
        on_timeout=data.on_timeout,
        escalate_to=data.escalate_to,
        cooldown_max=data.cooldown_max,
        blackout_start=_parse_time(data.blackout_start),
        blackout_end=_parse_time(data.blackout_end),
        pre_approval=data.pre_approval,
        context_template=data.context_template,
        partial_approval=data.partial_approval,
        quorum_window=data.quorum_window,
        priority=data.priority,
        step_up_model=data.step_up_model,
        step_up_conditions=[c.model_dump() for c in data.step_up_conditions] if data.step_up_conditions else None,
        approval_checklist=data.approval_checklist,
        max_requests_per_hour=data.max_requests_per_hour,
        approval_expiry_seconds=data.approval_expiry_seconds,
        trigger_rules=data.trigger_rules,
        on_approve_actions=data.on_approve_actions,
        risk_auto_approve_threshold=data.risk_auto_approve_threshold,
        reauth_every_n=data.reauth_every_n,
        budget_limits=data.budget_limits,
        allowed_days=data.allowed_days,
    )
    db.add(rule)
    await db.flush()

    for i, approver_id in enumerate(data.approver_ids):
        ra = RuleApprover(rule_id=rule.id, approver_id=approver_id, order=i)
        db.add(ra)

    await db.commit()
    await db.refresh(rule)
    return RuleResponse(**_rule_to_response(rule))


@router.get("")
async def list_rules(
    db: AsyncSession = Depends(get_db),
    ws_id: uuid.UUID = Depends(_resolve_workspace_id),
):
    result = await db.execute(
        select(Rule)
        .where(Rule.workspace_id == ws_id)
        .order_by(Rule.priority.desc(), Rule.created_at.desc())
    )
    rules = result.scalars().all()
    return [_rule_to_response(r) for r in rules]


@router.get("/templates")
async def list_templates(
    category: str | None = Query(None, description="Filter by category: finance, devops, communication, compliance"),
):
    """Return pre-built rule templates for common scenarios."""
    templates = RULE_TEMPLATES
    if category:
        templates = [t for t in templates if t.get("category") == category]
    return {
        "templates": templates,
        "categories": sorted(set(t["category"] for t in RULE_TEMPLATES)),
    }


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Return a specific rule template by ID."""
    for t in RULE_TEMPLATES:
        if t["id"] == template_id:
            return t
    raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _fga: None = Depends(require_rule_read),
):
    result = await db.execute(select(Rule).where(Rule.id == uuid.UUID(rule_id)))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return RuleResponse(**_rule_to_response(rule))


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    data: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    _fga: None = Depends(require_rule_write),
):
    result = await db.execute(select(Rule).where(Rule.id == uuid.UUID(rule_id)))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = data.model_dump(exclude_unset=True)

    if "conditions" in update_data and update_data["conditions"] is not None:
        update_data["conditions"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in update_data["conditions"]]
    if "step_up_conditions" in update_data and update_data["step_up_conditions"] is not None:
        update_data["step_up_conditions"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in update_data["step_up_conditions"]]
    if "blackout_start" in update_data:
        update_data["blackout_start"] = _parse_time(update_data["blackout_start"])
    if "blackout_end" in update_data:
        update_data["blackout_end"] = _parse_time(update_data["blackout_end"])

    approver_ids = update_data.pop("approver_ids", None)
    for key, value in update_data.items():
        setattr(rule, key, value)

    if approver_ids is not None:
        existing = await db.execute(select(RuleApprover).where(RuleApprover.rule_id == rule.id))
        for ra in existing.scalars().all():
            await db.delete(ra)
        for i, approver_id in enumerate(approver_ids):
            ra = RuleApprover(rule_id=rule.id, approver_id=approver_id, order=i)
            db.add(ra)

    await db.commit()
    await db.refresh(rule)
    return RuleResponse(**_rule_to_response(rule))


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _fga: None = Depends(require_rule_write),
):
    result = await db.execute(select(Rule).where(Rule.id == uuid.UUID(rule_id)))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = False
    await db.commit()
    return {"status": "deactivated"}


@router.post("/simulate")
async def simulate_rule(
    connection: str,
    action: str,
    params: dict,
    ws_id: uuid.UUID = Depends(_resolve_workspace_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Rule).where(
            Rule.workspace_id == ws_id,
            Rule.connection == connection,
            Rule.action == action,
            Rule.is_active.is_(True),
        ).order_by(Rule.priority.desc())
    )
    rules = result.scalars().all()

    matched = None
    for rule in rules:
        if evaluate_conditions(rule.conditions or [], params):
            matched = rule
            break

    if not matched:
        return {
            "matched": False,
            "message": "No matching rule — would auto-approve",
        }

    approvers = [
        {"id": str(ra.approver_id), "name": ra.approver.name if ra.approver else "Unknown", "order": ra.order}
        for ra in matched.rule_approvers
    ]

    step_up_triggered = False
    effective_model = matched.model
    if matched.step_up_conditions and matched.step_up_model:
        if evaluate_conditions(matched.step_up_conditions, params):
            step_up_triggered = True
            effective_model = matched.step_up_model

    # Full dry-run simulation
    risk = compute_risk_score(params, rule=matched)
    time_window = check_time_window(matched)
    required_count = get_required_approval_count(matched)
    escalation_chain = build_escalation_chain(matched)

    return {
        "matched": True,
        "rule_id": str(matched.id),
        "rule_name": matched.name,
        "model": matched.model.value if isinstance(matched.model, ApprovalModel) else matched.model,
        "effective_model": effective_model.value if isinstance(effective_model, ApprovalModel) else effective_model,
        "step_up_triggered": step_up_triggered,
        "approvers": approvers,
        "required_approvals": required_count,
        "timeout_seconds": matched.timeout_seconds,
        "on_timeout": matched.on_timeout.value if isinstance(matched.on_timeout, TimeoutAction) else matched.on_timeout,
        "binding_message": render_binding_message(matched.context_template, params),
        "escalation": str(matched.escalate_to) if matched.escalate_to else None,
        "escalation_chain": escalation_chain,
        "risk": risk,
        "time_window": time_window,
        "blackout_active": is_in_blackout(matched),
        "blackout": {
            "start": matched.blackout_start.isoformat() if matched.blackout_start else None,
            "end": matched.blackout_end.isoformat() if matched.blackout_end else None,
        },
        "dry_run": True,
    }
