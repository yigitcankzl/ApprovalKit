"""
A2A (Agent-to-Agent) Server
============================
Exposes the Healthcare AI Agent as a Google A2A-compliant agent.
Other A2A agents can discover skills via /.well-known/agent.json
and send tasks via JSON-RPC 2.0 at /a2a endpoint.
"""
import uuid
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Response
from a2a.agent_card import AGENT_CARD

logger = logging.getLogger("healthcare.a2a")

router = APIRouter(tags=["a2a"])


@router.get("/.well-known/agent.json")
async def get_agent_card():
    return AGENT_CARD


@router.post("/a2a")
async def handle_a2a(request: Request):
    """
    A2A JSON-RPC 2.0 endpoint.
    Supports: tasks/send, tasks/get
    """
    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    rpc_id = body.get("id", str(uuid.uuid4()))

    if method == "tasks/send":
        return await _handle_task_send(rpc_id, params)
    elif method == "tasks/get":
        return await _handle_task_get(rpc_id, params)
    else:
        return _rpc_error(rpc_id, -32601, f"Method not found: {method}")


# In-memory task store for demo purposes
_tasks: dict[str, dict] = {}


async def _handle_task_send(rpc_id: str, params: dict) -> dict:
    """Handle tasks/send — create a new task from A2A message."""
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    parts = message.get("parts", [])

    # Extract the request from message parts
    request_data = {}
    skill_id = None
    for part in parts:
        if part.get("type") == "application/json":
            request_data = json.loads(part["data"]) if isinstance(part["data"], str) else part["data"]
        if part.get("metadata", {}).get("skill"):
            skill_id = part["metadata"]["skill"]

    if not skill_id and request_data.get("skill"):
        skill_id = request_data["skill"]

    # Map skill to internal operation
    result_text = f"Task received for skill: {skill_id}"
    status = "completed"

    try:
        if skill_id == "lookup-patient":
            mrn = request_data.get("mrn", "MRN-00001")
            result_text = json.dumps({
                "skill": "lookup-patient",
                "result": {
                    "mrn": mrn,
                    "message": f"Use GET /api/patients/mrn/{mrn} on the Healthcare Agent API to look up this patient",
                    "api_url": f"http://localhost:3002/api/patients/mrn/{mrn}",
                },
            })
        elif skill_id in ("register-patient", "prescribe-medication", "dose-change",
                          "external-referral", "insurance-data", "process-billing",
                          "emergency-access", "security-breach", "delegate-doctor"):
            result_text = json.dumps({
                "skill": skill_id,
                "status": "submitted",
                "message": (
                    f"Task for '{skill_id}' has been submitted to the Healthcare Agent. "
                    f"This operation requires ApprovalKit approval. "
                    f"Monitor progress via the dashboard at http://localhost:3003"
                ),
                "params": request_data,
            })
            status = "working"
        else:
            result_text = json.dumps({"error": f"Unknown skill: {skill_id}"})
            status = "failed"

    except Exception as e:
        result_text = json.dumps({"error": str(e)})
        status = "failed"

    task = {
        "id": task_id,
        "status": {"state": status},
        "artifacts": [
            {
                "parts": [
                    {"type": "application/json", "data": result_text}
                ],
            }
        ],
        "history": [
            {
                "role": "agent",
                "parts": [{"type": "text/plain", "data": f"Processing skill: {skill_id}"}],
            }
        ],
        "metadata": {
            "created_at": datetime.utcnow().isoformat(),
            "skill": skill_id,
        },
    }
    _tasks[task_id] = task

    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "result": task,
    }


async def _handle_task_get(rpc_id: str, params: dict) -> dict:
    """Handle tasks/get — retrieve task status."""
    task_id = params.get("id", "")
    task = _tasks.get(task_id)
    if not task:
        return _rpc_error(rpc_id, -32602, f"Task not found: {task_id}")

    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "result": task,
    }


def _rpc_error(rpc_id: str, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {"code": code, "message": message},
    }
