"""
Registered Agents
=================
CRUD for user-defined agents stored in the dashboard.
GET  /api/v1/agents        — list all agents (with scenarios)
POST /api/v1/agents        — create agent + optional scenarios
DELETE /api/v1/agents/{id} — delete agent and its scenarios
POST /api/v1/agents/{id}/scenarios — add a scenario to an existing agent
"""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.agent import RegisteredAgent, AgentScenario
from api.models.connection import ServiceConnection
from api.models.workspace import Workspace

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

async def _get_workspace(db: AsyncSession) -> Workspace:
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=400, detail="No active workspace found")
    return ws


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
async def list_agents(db: AsyncSession = Depends(get_db)):
    ws = await _get_workspace(db)
    result = await db.execute(
        select(RegisteredAgent)
        .where(RegisteredAgent.workspace_id == ws.id)
        .order_by(RegisteredAgent.created_at.desc())
    )
    agents = result.scalars().all()
    return [_agent_to_dict(a) for a in agents]


@router.post("", status_code=201)
async def create_agent(body: AgentIn, db: AsyncSession = Depends(get_db)):
    ws = await _get_workspace(db)

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
        api_key=agent_api_key,
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
    return _agent_to_dict(agent, include_key=True)


@router.post("/{agent_id}/scenarios", status_code=201)
async def add_scenario(agent_id: str, body: ScenarioIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == uuid.UUID(agent_id))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

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
async def update_scenario(agent_id: str, scenario_id: str, body: ScenarioIn, db: AsyncSession = Depends(get_db)):
    """Update an existing scenario on an agent."""
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
async def delete_scenario(agent_id: str, scenario_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a scenario from an agent."""
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
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == uuid.UUID(agent_id))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/regenerate-key")
async def regenerate_api_key(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Generate a new API key for this agent. Old key stops working immediately."""
    result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == uuid.UUID(agent_id))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.api_key = f"ak_{secrets.token_urlsafe(32)}"
    await db.commit()
    return {"api_key": agent.api_key}


@router.post("/{agent_id}/revoke")
async def revoke_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Disable this agent's API key. Agent can no longer make requests."""
    result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == uuid.UUID(agent_id))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = False
    agent.api_key = None
    await db.commit()
    return {"status": "revoked", "agent": agent.name}
