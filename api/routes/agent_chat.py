"""
Agent Chat Endpoint
===================
POST /api/v1/demo/agents/{agent_id}/chat
POST /api/v1/demo/agents/{agent_id}/chat/stream
GET  /api/v1/demo/agents/{agent_id}/suggestions
DELETE /api/v1/demo/agents/{agent_id}/session/{session_id}
GET  /api/v1/demo/ollama-status

AI API key is stored encrypted in the user's workspace.
Decrypted at runtime, never exposed to the frontend after initial save.
"""

import json
import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
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


def _resolve_ai_credentials(workspace: Workspace) -> tuple[str, str]:
    """Resolve AI API key and provider from workspace config.

    Returns (provider, api_key). For Ollama, api_key may be empty.
    """
    api_key = ""
    provider = "gemini"
    if workspace.ai_api_key_encrypted == "vault":
        vault_data = read_secret(str(workspace.id), _AI_KEY_SLUG)
        if vault_data:
            api_key = vault_data.get("api_key", "")
            provider = vault_data.get("provider", "gemini")
    elif workspace.ai_api_key_encrypted:
        decrypted = decrypt_secret(workspace.ai_api_key_encrypted) or ""
        if ":" in decrypted:
            provider, api_key = decrypted.split(":", 1)
        else:
            api_key = decrypted

    # Ollama doesn't need an API key
    if provider == "ollama":
        api_key = api_key or "ollama"

    return provider, api_key


@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(
    agent_id: str,
    req: ChatRequest,
    workspace: Workspace = Depends(get_current_workspace),
):
    provider, api_key = _resolve_ai_credentials(workspace)

    result = process_message(
        agent_id, req.message, req.agent_title, req.session_id,
        api_key=api_key, provider=provider,
        workspace_id=str(workspace.owner_auth0_sub or workspace.id),
    )
    return ChatResponse(**result)


@router.get("/{agent_id}/suggestions")
async def get_agent_suggestions(agent_id: str):
    return {"suggestions": get_suggestions(agent_id)}


@router.delete("/{agent_id}/session/{session_id}")
async def delete_session(agent_id: str, session_id: str):
    clear_session(f"{agent_id}:{session_id}")
    return {"status": "cleared"}


@router.get("/ollama-status")
async def check_ollama():
    """Check if Ollama is running and which models are available."""
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://localhost:11434/api/tags")
            models = r.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            has_model = any("llama3.1" in n or "llama3.2" in n or "llama3.3" in n for n in model_names)
            return {"running": True, "has_model": has_model, "models": model_names}
    except Exception:
        return {"running": False, "has_model": False, "models": []}
