"""
Registered Agents
=================
CRUD for user-defined agents stored in the dashboard.
GET  /api/v1/agents        — list all agents (with scenarios)
POST /api/v1/agents        — create agent + optional scenarios
DELETE /api/v1/agents/{id} — delete agent and its scenarios
POST /api/v1/agents/{id}/scenarios — add a scenario to an existing agent
"""
import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from api.database import get_db
from api.models.agent import RegisteredAgent, AgentScenario
from api.models.connection import ServiceConnection
from api.models.approval_job import ApprovalJob
from api.models.workspace import Workspace
from api.middleware.workspace import get_current_workspace
from api.middleware.auth import verify_hmac_signature

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ScenarioIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    connection: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=100)
    params: dict = Field(default_factory=dict)


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    icon: str = "bot"
    allowed_connections: list[str] | None = None
    scenarios: list[ScenarioIn] = Field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _agent_to_dict(agent: RegisteredAgent, include_key: bool = False) -> dict:
    d = {
        "id": str(agent.id),
        "name": agent.name,
        "description": agent.description,
        "icon": agent.icon,
        "is_active": agent.is_active if agent.is_active is not None else True,
        "allowed_connections": agent.allowed_connections,
        "has_api_key": bool(agent.api_key),
        "api_key_preview": f"{agent.api_key[:8]}...{agent.api_key[-4:]}" if agent.api_key else None,
        "created_at": agent.created_at.isoformat(),
        "scenarios": [
            {
                "id": str(s.id),
                "title": s.title,
                "connection": s.connection,
                "action": s.action,
                "params": s.params,
            }
            for s in (agent.scenarios or [])
        ],
    }
    if include_key and agent.api_key:
        d["api_key"] = agent.api_key
    return d


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_agents(ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RegisteredAgent)
        .where(RegisteredAgent.workspace_id == ws.id)
        .order_by(RegisteredAgent.created_at.desc())
    )
    agents = result.scalars().all()
    return [_agent_to_dict(a) for a in agents]


@router.post("", status_code=201)
async def create_agent(body: AgentIn, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):

    # Validate allowed_connections against existing slugs
    if body.allowed_connections:
        result = await db.execute(
            select(ServiceConnection.slug).where(ServiceConnection.workspace_id == ws.id)
        )
        valid_slugs = {row[0] for row in result.all()}
        invalid = [c for c in body.allowed_connections if c not in valid_slugs]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown connections: {', '.join(invalid)}. Valid: {', '.join(sorted(valid_slugs))}",
            )

    agent_api_key = f"ak_{secrets.token_urlsafe(32)}"
    agent = RegisteredAgent(
        workspace_id=ws.id,
        name=body.name,
        description=body.description,
        icon=body.icon,
        api_key=hashlib.sha256(agent_api_key.encode()).hexdigest(),  # Hash only — plaintext shown once
        allowed_connections=body.allowed_connections,
        is_active=True,
    )
    db.add(agent)
    await db.flush()

    for sc in body.scenarios:
        scenario = AgentScenario(
            agent_id=agent.id,
            title=sc.title,
            connection=sc.connection,
            action=sc.action,
            params=sc.params,
        )
        db.add(scenario)

    await db.commit()
    await db.refresh(agent)
    result = _agent_to_dict(agent, include_key=False)
    result["api_key"] = agent_api_key  # Plaintext — shown once, never stored
    return result


async def _get_agent_for_workspace(agent_id: str, ws: Workspace, db: AsyncSession) -> RegisteredAgent:
    result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == uuid.UUID(agent_id), RegisteredAgent.workspace_id == ws.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{agent_id}/scenarios", status_code=201)
async def add_scenario(agent_id: str, body: ScenarioIn, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    agent = await _get_agent_for_workspace(agent_id, ws, db)

    scenario = AgentScenario(
        agent_id=agent.id,
        title=body.title,
        connection=body.connection,
        action=body.action,
        params=body.params,
    )
    db.add(scenario)
    await db.commit()
    return {"id": str(scenario.id), "title": scenario.title}


@router.put("/{agent_id}/scenarios/{scenario_id}")
async def update_scenario(agent_id: str, scenario_id: str, body: ScenarioIn, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Update an existing scenario on an agent."""
    await _get_agent_for_workspace(agent_id, ws, db)  # verify ownership
    result = await db.execute(
        select(AgentScenario).where(
            AgentScenario.id == uuid.UUID(scenario_id),
            AgentScenario.agent_id == uuid.UUID(agent_id),
        )
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    scenario.title = body.title
    scenario.connection = body.connection
    scenario.action = body.action
    scenario.params = body.params
    await db.commit()
    return {"id": str(scenario.id), "title": scenario.title}


@router.delete("/{agent_id}/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(agent_id: str, scenario_id: str, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Delete a scenario from an agent."""
    await _get_agent_for_workspace(agent_id, ws, db)
    result = await db.execute(
        select(AgentScenario).where(
            AgentScenario.id == uuid.UUID(scenario_id),
            AgentScenario.agent_id == uuid.UUID(agent_id),
        )
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    await db.delete(scenario)
    await db.commit()


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    agent = await _get_agent_for_workspace(agent_id, ws, db)
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/regenerate-key")
async def regenerate_api_key(agent_id: str, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Generate a new API key for this agent. Old key stops working immediately."""
    agent = await _get_agent_for_workspace(agent_id, ws, db)
    new_key = f"ak_{secrets.token_urlsafe(32)}"
    agent.api_key = hashlib.sha256(new_key.encode()).hexdigest()  # Hash only
    await db.commit()
    return {"api_key": new_key}  # Plaintext shown once, never stored


@router.post("/{agent_id}/revoke")
async def revoke_agent(agent_id: str, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Disable this agent's API key. Agent can no longer make requests."""
    agent = await _get_agent_for_workspace(agent_id, ws, db)
    agent.is_active = False
    agent.api_key = None
    await db.commit()
    return {"status": "revoked", "agent": agent.name}


# ── Bootstrap (single-call provisioning) ─────────────────────────────────────


class BootstrapApprover(BaseModel):
    name: str
    email: str
    role: str


class BootstrapCondition(BaseModel):
    field: str
    operator: str
    value: str | int | float | bool | list | None = None


class BootstrapRule(BaseModel):
    name: str
    connection: str
    action: str
    model: str  # any_one, specific, all_of_n, k_of_n, sequential
    approvers: list[str]  # role names
    conditions: list[BootstrapCondition] = Field(default_factory=list)
    timeout_seconds: int = 300
    priority: int = 0
    partial_approval: bool = False
    context_template: str | None = None
    step_up_conditions: list[BootstrapCondition] | None = None
    step_up_model: str | None = None
    on_timeout: str | None = None
    escalate_to: str | None = None
    blackout_start: str | None = None
    blackout_end: str | None = None


class BootstrapConnection(BaseModel):
    slug: str
    name: str
    service: str
    actions: list[str]


class BootstrapBody(BaseModel):
    agent: AgentIn
    connections: list[BootstrapConnection] = Field(default_factory=list)
    approvers: list[BootstrapApprover] = Field(default_factory=list)
    rules: list[BootstrapRule] = Field(default_factory=list)


@router.post("/bootstrap", status_code=201)
async def bootstrap_agent(
    body: BootstrapBody,
    ws: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """
    One-call provisioning: register an agent with its full config.
    Creates connections, approvers, rules, and scenarios in one shot.
    Idempotent — skips resources that already exist (matched by slug/email/name).
    """
    from api.models.approver import Approver
    from api.models.rule import Rule, RuleApprover

    created = {"agent": None, "connections": 0, "approvers": 0, "rules": 0, "scenarios": 0}

    # 1. Agent
    existing_agent = await db.execute(
        select(RegisteredAgent).where(
            RegisteredAgent.workspace_id == ws.id,
            RegisteredAgent.name == body.agent.name,
        ).limit(1)
    )
    agent = existing_agent.scalar_one_or_none()
    agent_api_key = None
    if not agent:
        agent_api_key = f"ak_{secrets.token_urlsafe(32)}"
        agent = RegisteredAgent(
            workspace_id=ws.id,
            name=body.agent.name,
            description=body.agent.description,
            icon=body.agent.icon,
            api_key=hashlib.sha256(agent_api_key.encode()).hexdigest(),
            is_active=True,
        )
        db.add(agent)
        await db.flush()
        created["agent"] = body.agent.name
    else:
        agent.description = body.agent.description or agent.description
        agent.icon = body.agent.icon or agent.icon

    # Scenarios (replace all)
    old_scenarios = await db.execute(
        select(AgentScenario).where(AgentScenario.agent_id == agent.id)
    )
    for old in old_scenarios.scalars().all():
        await db.delete(old)
    for sc in body.agent.scenarios:
        db.add(AgentScenario(
            agent_id=agent.id,
            title=sc.title, connection=sc.connection,
            action=sc.action, params=sc.params,
        ))
        created["scenarios"] += 1

    # 2. Connections
    for conn in body.connections:
        existing = await db.execute(
            select(ServiceConnection).where(
                ServiceConnection.workspace_id == ws.id,
                ServiceConnection.slug == conn.slug,
            ).limit(1)
        )
        if not existing.scalar_one_or_none():
            db.add(ServiceConnection(
                workspace_id=ws.id,
                name=conn.name,
                service=conn.service,
                slug=conn.slug,
                actions=conn.actions,
                is_active=True,
            ))
            created["connections"] += 1

    # 3. Approvers
    approver_map: dict[str, uuid.UUID] = {}
    for appr in body.approvers:
        existing = await db.execute(
            select(Approver).where(
                Approver.workspace_id == ws.id,
                Approver.email == appr.email,
            ).limit(1)
        )
        row = existing.scalar_one_or_none()
        if row:
            approver_map[appr.role] = row.id
        else:
            new_approver = Approver(
                workspace_id=ws.id,
                name=appr.name,
                email=appr.email,
                auth0_user_id=f"auth0|{appr.email.split('@')[0]}",
                is_active=True,
            )
            db.add(new_approver)
            await db.flush()
            approver_map[appr.role] = new_approver.id
            created["approvers"] += 1

    # 4. Rules
    for rule_in in body.rules:
        existing = await db.execute(
            select(Rule).where(
                Rule.workspace_id == ws.id,
                Rule.name == rule_in.name,
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            continue

        approver_ids = [approver_map[r] for r in rule_in.approvers if r in approver_map]
        if not approver_ids:
            logger.warning(f"Bootstrap: skipping rule '{rule_in.name}' — no matching approvers")
            continue

        rule = Rule(
            workspace_id=ws.id,
            name=rule_in.name,
            connection=rule_in.connection,
            action=rule_in.action,
            conditions=[c.model_dump() for c in rule_in.conditions],
            model=rule_in.model,
            timeout_seconds=rule_in.timeout_seconds,
            priority=rule_in.priority,
            partial_approval=rule_in.partial_approval,
            context_template=rule_in.context_template,
            is_active=True,
        )
        if rule_in.step_up_conditions:
            rule.step_up_conditions = [c.model_dump() for c in rule_in.step_up_conditions]
            rule.step_up_model = rule_in.step_up_model or "all_of_n"
        if rule_in.blackout_start:
            from api.utils import parse_time
            rule.blackout_start = parse_time(rule_in.blackout_start)
            rule.blackout_end = parse_time(rule_in.blackout_end) if rule_in.blackout_end else None
        if rule_in.on_timeout == "escalate":
            rule.on_timeout = "escalate"
            if rule_in.escalate_to and rule_in.escalate_to in approver_map:
                rule.escalate_to = approver_map[rule_in.escalate_to]

        db.add(rule)
        await db.flush()

        for i, aid in enumerate(approver_ids):
            db.add(RuleApprover(rule_id=rule.id, approver_id=aid, order=i))
        created["rules"] += 1

    await db.commit()

    result = {
        "status": "provisioned",
        "created": created,
        "agent_id": str(agent.id),
    }
    if agent_api_key:
        result["api_key"] = agent_api_key
        result["hmac_secret"] = "Use your workspace HMAC secret"
    return result
