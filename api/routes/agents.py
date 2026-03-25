"""
Registered Agents
=================
CRUD for user-defined agents stored in the dashboard.
GET  /api/v1/agents        — list all agents (with scenarios)
POST /api/v1/agents        — create agent + optional scenarios
DELETE /api/v1/agents/{id} — delete agent and its scenarios
POST /api/v1/agents/{id}/scenarios — add a scenario to an existing agent
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.agent import RegisteredAgent, AgentScenario
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


def _agent_to_dict(agent: RegisteredAgent) -> dict:
    return {
        "id": str(agent.id),
        "name": agent.name,
        "description": agent.description,
        "icon": agent.icon,
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
    agent = RegisteredAgent(
        workspace_id=ws.id,
        name=body.name,
        description=body.description,
        icon=body.icon,
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
    return _agent_to_dict(agent)


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
