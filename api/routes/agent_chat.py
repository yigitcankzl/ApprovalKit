"""
Agent Chat Endpoint
===================
POST /api/v1/demo/agents/{agent_id}/chat
GET  /api/v1/demo/agents/{agent_id}/suggestions
DELETE /api/v1/demo/agents/{agent_id}/session/{session_id}

AI API key is stored encrypted in the user's workspace.
Decrypted at runtime, never exposed to the frontend after initial save.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.workspace import Workspace
from api.middleware.workspace import get_current_workspace
from api.services.encryption import decrypt_secret
from api.services.vault import read_secret
from api.services.agent_chat import process_message, get_suggestions, clear_session

_AI_KEY_SLUG = "_ai_api_key"

router = APIRouter(prefix="/api/v1/demo/agents", tags=["agent-chat"])


class ChatRequest(BaseModel):
    message: str
    agent_title: str = ""
    session_id: str = ""


class ChatResponse(BaseModel):
    response: str
    action: dict | None = None
    suggestions: list[str] = []
    type: str = "chat"
    session_id: str = ""


@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(
    agent_id: str,
    req: ChatRequest,
    workspace: Workspace = Depends(get_current_workspace),
):
    # Read AI API key: Vault first, then Fernet fallback
    api_key = ""
    if workspace.ai_api_key_encrypted == "vault":
        vault_data = read_secret(str(workspace.id), _AI_KEY_SLUG)
        if vault_data:
            api_key = vault_data.get("api_key", "")
    elif workspace.ai_api_key_encrypted:
        api_key = decrypt_secret(workspace.ai_api_key_encrypted) or ""

    result = process_message(agent_id, req.message, req.agent_title, req.session_id, api_key=api_key)
    return ChatResponse(**result)


@router.get("/{agent_id}/suggestions")
async def get_agent_suggestions(agent_id: str):
    return {"suggestions": get_suggestions(agent_id)}


@router.delete("/{agent_id}/session/{session_id}")
async def delete_session(agent_id: str, session_id: str):
    clear_session(f"{agent_id}:{session_id}")
    return {"status": "cleared"}
