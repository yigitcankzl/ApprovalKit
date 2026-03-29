"""
Healthcare AI Chat — LLM-powered conversational agent
Uses Groq (Llama 3.3 70B) to understand natural language and
call ApprovalKit-gated healthcare actions.
"""
import json
import os
import uuid
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.approval_gateway import ApprovalGateway

gateway = ApprovalGateway()

logger = logging.getLogger("healthcare.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# ── Tool definitions for LLM ─────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "prescribe_medication",
            "description": "Prescribe medication to a patient. Routine meds need doctor approval, controlled substances need doctor + pharmacist approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "Patient name"},
                    "patient_id": {"type": "string", "description": "Patient MRN (e.g. MRN-00001)"},
                    "medication_name": {"type": "string", "description": "Medication name"},
                    "dosage": {"type": "string", "description": "Dosage (e.g. 500mg)"},
                    "is_controlled": {"type": "boolean", "description": "Whether this is a controlled substance (narcotics, stimulants, etc.)"},
                },
                "required": ["patient_name", "medication_name", "dosage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "process_billing",
            "description": "Process a billing charge for a patient. Under $500 auto-approves, $500-$10k needs manager, above $10k needs manager + CFO.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string"},
                    "patient_id": {"type": "string"},
                    "amount": {"type": "number", "description": "Amount in USD"},
                    "description": {"type": "string", "description": "What the charge is for"},
                },
                "required": ["patient_name", "amount", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "share_patient_records",
            "description": "Share patient medical records with an external clinic, insurance company, or research institution. Requires appropriate approvals based on recipient type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string"},
                    "patient_id": {"type": "string"},
                    "recipient_name": {"type": "string", "description": "Name of the recipient organization"},
                    "recipient_type": {"type": "string", "enum": ["external_clinic", "insurance", "research"], "description": "Type of recipient"},
                    "purpose": {"type": "string", "description": "Reason for sharing"},
                },
                "required": ["patient_name", "recipient_name", "recipient_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "emergency_access",
            "description": "Request emergency access to patient records. Uses fast-track approval (any available doctor, 2-minute timeout).",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string"},
                    "patient_id": {"type": "string"},
                    "reason": {"type": "string", "description": "Emergency reason"},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium"]},
                },
                "required": ["patient_name", "reason", "severity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Send an email notification to a patient, doctor, or staff member.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_email": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["recipient_email", "subject", "body"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are a healthcare AI assistant at MedCore General Hospital. You help doctors and staff manage patient care by executing actions through ApprovalKit — a human approval system.

When a user asks you to do something, use the available tools. Important:
- Prescriptions for controlled substances (opioids, stimulants, benzodiazepines like Adderall, Oxycodone, Xanax) set is_controlled=true
- Billing charges under $500 auto-approve, above need human approval
- Patient record sharing requires approval based on recipient type
- Emergency access uses fast-track (2-minute timeout)
- You don't have direct access to medications or billing systems — everything goes through ApprovalKit for approval first

Always explain what you're doing and what approvals are needed. Be concise and professional."""

# ── Session storage ───────────────────────────────────────────────────────────

_sessions: dict[str, list[dict]] = {}

# ── Tool execution ────────────────────────────────────────────────────────────

async def execute_tool(name: str, args: dict) -> dict:
    """Execute a tool call by routing to ApprovalKit gateway."""
    try:
        patient_name = args.get("patient_name", "Unknown Patient")
        patient_id = args.get("patient_id", "MRN-00001")

        if name == "prescribe_medication":
            if args.get("is_controlled"):
                result = await gateway.approve_controlled_substance(
                    medication_name=args["medication_name"],
                    dosage=args["dosage"],
                    schedule_class=args.get("schedule_class", "II"),
                    patient_mrn=patient_id,
                    patient_name=patient_name,
                    doctor_name="AI Healthcare Agent",
                )
            else:
                result = await gateway.approve_routine_prescription(
                    medication_name=args["medication_name"],
                    dosage=args["dosage"],
                    patient_mrn=patient_id,
                    patient_name=patient_name,
                    doctor_name="AI Healthcare Agent",
                )
            return {"status": "approved", "action": f"Prescribed {args['medication_name']} {args['dosage']} for {patient_name}", **result}

        elif name == "process_billing":
            result = await gateway.approve_billing(
                invoice_number=f"INV-{uuid.uuid4().hex[:6].upper()}",
                patient_name=patient_name,
                description=args["description"],
                amount=args["amount"],
            )
            return {"status": "approved", "action": f"Processed ${args['amount']} charge: {args['description']}", **result}

        elif name == "share_patient_records":
            if args.get("recipient_type") == "insurance":
                result = await gateway.approve_insurance_data_request(
                    patient_mrn=patient_id,
                    patient_name=patient_name,
                    insurance_name=args["recipient_name"],
                    requested_data_scope=args.get("purpose", "medical records"),
                    reason=args.get("purpose", "insurance review"),
                )
            else:
                result = await gateway.approve_external_referral(
                    patient_mrn=patient_id,
                    patient_name=patient_name,
                    clinic_name=args["recipient_name"],
                    reason=args.get("purpose", "specialist consultation"),
                    data_scope="medical records",
                )
            return {"status": "approved", "action": f"Shared records with {args['recipient_name']}", **result}

        elif name == "emergency_access":
            result = await gateway.approve_emergency_access(
                patient_mrn=patient_id,
                patient_name=patient_name,
                reason=args["reason"],
                triggered_by="AI Healthcare Agent",
            )
            return {"status": "approved", "action": f"Emergency access granted for {patient_name}", **result}

        elif name == "send_notification":
            result = await gateway.send_email(
                recipient=args["recipient_email"],
                subject=args["subject"],
                body=args["body"],
            )
            return {"status": "sent", "action": f"Email sent to {args['recipient_email']}", **result}

        return {"status": "error", "message": f"Unknown tool: {name}"}

    except Exception as e:
        error_msg = str(e)
        if "ApprovalDenied" in type(e).__name__ or "Approval" in error_msg:
            return {"status": "denied", "message": f"Approval denied: {error_msg}"}
        return {"status": "error", "message": error_msg}


# ── Chat endpoint ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""

class ChatResponse(BaseModel):
    response: str
    session_id: str
    actions: list[dict] = []

@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    if session_id not in _sessions:
        _sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    history = _sessions[session_id]
    history.append({"role": "user", "content": req.message})

    actions_taken: list[dict] = []

    # Agentic loop — up to 5 rounds of tool calls
    for _ in range(5):
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/v1/chat/completions",
                headers={"Authorization": "Bearer ollama", "Content-Type": "application/json"},
                json={
                    "model": OLLAMA_MODEL,
                    "messages": history,
                    "tools": TOOLS,
                    "tool_choice": "auto",
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )

        if resp.status_code != 200:
            logger.error(f"Ollama API error: {resp.status_code} {resp.text[:200]}")
            return ChatResponse(
                response="Sorry, I couldn't process your request. Make sure Ollama is running with qwen2.5:7b.",
                session_id=session_id,
            )

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]

        # Add assistant message to history
        history.append(msg)

        # If no tool calls, we're done
        if not msg.get("tool_calls"):
            _sessions[session_id] = history[-20:]  # Keep last 20 messages
            return ChatResponse(
                response=msg.get("content", ""),
                session_id=session_id,
                actions=actions_taken,
            )

        # Execute tool calls
        for tc in msg["tool_calls"]:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"])

            logger.info(f"Tool call: {fn_name}({fn_args})")
            result = await execute_tool(fn_name, fn_args)
            actions_taken.append({"tool": fn_name, "args": fn_args, "result": result})

            history.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result),
            })

    # If we exhausted rounds
    return ChatResponse(
        response="I've completed the requested actions.",
        session_id=session_id,
        actions=actions_taken,
    )


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"status": "cleared"}
