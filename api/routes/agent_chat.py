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
import logging
import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.database import get_db
from api.models.workspace import Workspace
from api.middleware.workspace import get_current_workspace
from api.services.encryption import decrypt_secret
from api.services.vault import read_secret
from api.services.agent_chat import process_message, get_suggestions, clear_session

_AI_KEY_SLUG = "_ai_api_key"

router = APIRouter(prefix="/api/v1/demo/agents", tags=["agent-chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=10000)
    agent_title: str = ""
    session_id: str = ""


class ChatResponse(BaseModel):
    response: str
    action: dict | None = None
    actions: list[dict] = []
    actions_taken: int = 0
    suggestions: list[str] = []
    type: str = "chat"
    session_id: str = ""
    rule_name: str | None = None
    message: str | None = None


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


@router.post("/{agent_id}/chat/stream")
async def chat_with_agent_stream(
    agent_id: str,
    req: ChatRequest,
    workspace: Workspace = Depends(get_current_workspace),
):
    """Streaming chat endpoint using Server-Sent Events.

    Sends events:
    - type=thinking: LLM is processing
    - type=token: incremental text token
    - type=tool_call: agent calling a tool
    - type=tool_result: result from tool execution
    - type=done: final response with summary
    """
    provider, api_key = _resolve_ai_credentials(workspace)
    workspace_id = str(workspace.owner_auth0_sub or workspace.id)

    async def event_generator():
        yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

        try:
            from api.services.agent_chat import (
                AGENT_PROMPTS, AGENT_TOOLS, AGENT_SUGGESTIONS,
                _PROVIDER_CONFIG, _execute_tool, _map_tool_to_action,
                _sessions, MAX_HISTORY,
            )
            from openai import OpenAI

            pconfig = _PROVIDER_CONFIG.get(provider, _PROVIDER_CONFIG.get("gemini", {}))
            if pconfig.get("type") != "openai":
                # Fall back to non-streaming for Gemini
                result = process_message(
                    agent_id, req.message, req.agent_title, req.session_id,
                    api_key=api_key, provider=provider, workspace_id=workspace_id,
                )
                yield f"data: {json.dumps({'type': 'token', 'content': result.get('response', '')})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'response': result.get('response', ''), 'session_id': result.get('session_id', '')})}\n\n"
                return

            client = OpenAI(api_key=api_key or "ollama", base_url=pconfig["base_url"], timeout=60)
            model = pconfig["model"]

            system_prompt = AGENT_PROMPTS.get(agent_id, f"You are a helpful AI assistant.")
            tools = AGENT_TOOLS.get(agent_id, [])

            session_id = req.session_id or ""
            if not session_id:
                import uuid
                session_id = str(uuid.uuid4())
            session_key = f"{agent_id}:{session_id}"
            if session_key not in _sessions:
                _sessions[session_key] = []
            history = _sessions[session_key]

            openai_tools = [
                {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
                for t in tools
            ]

            messages = [{"role": "system", "content": system_prompt}]
            for msg in history[-20:]:
                role = msg["role"]
                if role == "model":
                    role = "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})
            messages.append({"role": "user", "content": req.message})

            all_text = []
            all_actions = []

            for _round in range(5):
                stream = client.chat.completions.create(
                    model=model, messages=messages,
                    tools=openai_tools if openai_tools else None,
                    temperature=0.7, stream=True,
                )

                collected_content = ""
                collected_tool_calls: dict = {}

                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue

                    if delta.content:
                        collected_content += delta.content
                        yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in collected_tool_calls:
                                collected_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc.id:
                                collected_tool_calls[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    collected_tool_calls[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    collected_tool_calls[idx]["arguments"] += tc.function.arguments

                if collected_content:
                    all_text.append(collected_content)

                if not collected_tool_calls:
                    break

                # Build assistant message with tool calls
                msg_dict: dict = {"role": "assistant"}
                if collected_content:
                    msg_dict["content"] = collected_content
                tc_list = []
                for idx in sorted(collected_tool_calls.keys()):
                    tc = collected_tool_calls[idx]
                    tc_list.append({"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}})
                msg_dict["tool_calls"] = tc_list
                messages.append(msg_dict)

                # Execute tool calls — one at a time, wait for approval if pending
                for tc in tc_list:
                    try:
                        tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                    except json.JSONDecodeError:
                        tool_args = {}

                    yield f"data: {json.dumps({'type': 'tool_call', 'name': tc['function']['name'], 'args': tool_args})}\n\n"

                    try:
                        result = _execute_tool(agent_id, tc["function"]["name"], tool_args, workspace_id)
                    except Exception as tool_err:
                        logging.getLogger(__name__).error(f"Tool execution error: {tool_err}")
                        result = {"success": False, "status": "error", "error": str(tool_err)}

                    all_actions.append({"tool": tc["function"]["name"], "args": tool_args, "result": result})
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': tc['function']['name'], 'result': result})}\n\n"

                    # If pending approval, wait for human decision before continuing
                    job_id = result.get("job_id")
                    if result.get("status") == "pending" and job_id:
                        yield f"data: {json.dumps({'type': 'waiting_approval', 'job_id': job_id})}\n\n"
                        import asyncio
                        from sqlalchemy import select as _sel
                        from api.database import engine as _db_engine

                        final_status = "pending"
                        try:
                            from sqlalchemy.ext.asyncio import AsyncSession as _AS
                            from sqlalchemy.orm import sessionmaker as _sm
                            from api.models.approval_job import ApprovalJob

                            _engine = _db_engine
                            _async_session = _sm(_engine, class_=_AS, expire_on_commit=False)

                            for _poll in range(90):  # Max 3 minutes
                                await asyncio.sleep(2)
                                try:
                                    async with _async_session() as _db:
                                        _job = (await _db.execute(_sel(ApprovalJob).where(ApprovalJob.id == job_id))).scalar_one_or_none()
                                        if _job and _job.state.value in ("approved", "rejected", "timeout", "blocked"):
                                            final_status = _job.state.value
                                            break
                                except Exception:
                                    pass  # DB hiccup, retry next poll
                        except Exception as poll_err:
                            logging.getLogger(__name__).error(f"Approval poll error: {poll_err}")

                        if final_status == "pending":
                            final_status = "timeout"

                        yield f"data: {json.dumps({'type': 'approval_resolved', 'job_id': job_id, 'status': final_status})}\n\n"
                        tool_result_text = f"Action {final_status}. " + ("Approved and executed." if final_status == "approved" else f"Rejected/timed out by approver.")
                    else:
                        tool_result_text = json.dumps(result)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result_text if result.get("status") == "pending" else json.dumps(result),
                    })

            response_text = "\n".join(all_text).strip() or "Done."
            history.append({"role": "user", "content": req.message})
            history.append({"role": "model", "content": response_text})

            yield f"data: {json.dumps({'type': 'done', 'response': response_text, 'session_id': session_id, 'actions_taken': len(all_actions)})}\n\n"

        except Exception as e:
            logging.getLogger(__name__).error(f"Streaming chat error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
            r = await c.get("http://ollama:11434/api/tags")
            models = r.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            has_model = any("llama3.1" in n or "llama3.2" in n or "llama3.3" in n for n in model_names)
            return {"running": True, "has_model": has_model, "models": model_names}
    except Exception:
        return {"running": False, "has_model": False, "models": []}
