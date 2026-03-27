"""
Agent Chat Endpoint
===================
POST /api/v1/demo/agents/{agent_id}/chat

Processes user messages through the intent engine and returns
structured responses with optional actions to execute.
"""

from fastapi import APIRouter, Body
from pydantic import BaseModel

from api.services.agent_chat import process_message, get_suggestions

router = APIRouter(prefix="/api/v1/demo/agents", tags=["agent-chat"])


class ChatRequest(BaseModel):
    message: str
    agent_title: str = ""


class ChatResponse(BaseModel):
    response: str
    action: dict | None = None
    suggestions: list[str] = []
    type: str = "chat"  # "chat" or "action"


@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(agent_id: str, req: ChatRequest):
    """Process a chat message for a demo agent."""
    result = process_message(agent_id, req.message, req.agent_title)
    return ChatResponse(**result)


@router.get("/{agent_id}/suggestions")
async def get_agent_suggestions(agent_id: str):
    """Return suggested prompts for an agent."""
    return {"suggestions": get_suggestions(agent_id)}
