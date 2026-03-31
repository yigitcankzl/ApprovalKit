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
    allowed_tools: list[str] | None = None  # restrict to specific tools (for chain steps)


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
        allowed_tools=req.allowed_tools,
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


class OrchestrateRequest(BaseModel):
    message: str = Field(..., max_length=5000)


class OrchestrateStep(BaseModel):
    agent_id: str
    agent_title: str
    role: str
    allowed_tools: list[str]


class OrchestrateResponse(BaseModel):
    plan: list[OrchestrateStep]
    scenario: str


ORCHESTRATOR_PROMPT = """You are an AI workflow planner. Given a user's request, decide which specialized agents should handle it and in what order.

Before producing your plan, wrap your reasoning in <analysis> tags. Think through:
- What domains does this request touch?
- What is the correct order of operations? (action first, then notification)
- What are the security implications? (credentials NEVER leave Auth0 Token Vault)
- Which tools does each agent actually need? (least privilege — assign minimum tools)

Then output ONLY the JSON plan (no extra text outside the JSON).

STEP 1 — Identify the domain(s):
  FINANCE: payments, refunds, invoices, budgets, compensation
  SECURITY: breaches, access control, key rotation, lockdowns
  DEVOPS: deployments, releases, rollbacks, hotfixes
  HR: hiring, onboarding, offboarding, access provisioning
  COMPLIANCE: GDPR, data deletion, audits, transfers
  COMMUNICATION: emails, Slack, announcements (usually the LAST step)

STEP 2 — Select agents (one agent per domain, max 4):
  expense: process_refund, send_email, process_compensation, notify_slack, process_payment
  comms: send_slack, send_email, post_discord
  release_manager: deploy, rollback, notify_slack
  security_incident: log_alert, lock_repo, revoke_tokens, freeze_account, ban_account, issue_credit, rotate_key, rotate_all_keys
  recruitment: send_email, add_to_github, notify_slack, grant_access, revoke_access
  opensource: merge_pr, create_release, post_discord, pay_bounty
  research: provision_compute, submit_paper, purchase_dataset, notify_slack
  gdpr_request: process_deletion, process_transfer, send_compliance_email

STEP 3 — Assign each agent exactly 1-2 tools (least privilege).

SECURITY (defense-in-depth):
- Agents NEVER see or hold user credentials — all execution goes through Auth0 Token Vault
- Every action matching an approval rule requires explicit human consent before execution
- Agents operate under least-privilege: they only get the tools they need for their specific step

Rules:
- Each agent does ONE job — never overlap responsibilities
- Communication (comms) is usually the LAST step to notify about results
- Order: primary action first → investigation/follow-up → notification last
- RESPOND ONLY WITH VALID JSON

{"plan": [{"agent_id": "...", "agent_title": "... Agent", "role": "one sentence", "allowed_tools": ["tool1"]}, ...], "scenario": "one line summary"}

EXAMPLES:

User: "Customer got a defective product worth $420, needs refund and apology"
{"plan": [{"agent_id": "expense", "agent_title": "E-Commerce Agent", "role": "Process the $420 refund", "allowed_tools": ["process_refund"]}, {"agent_id": "comms", "agent_title": "Communications Agent", "role": "Send apology email and notify team", "allowed_tools": ["send_email", "send_slack"]}], "scenario": "Handle defective product refund and customer communication"}

User: "Security breach detected, lock repos and notify CTO"
{"plan": [{"agent_id": "security_incident", "agent_title": "Security Agent", "role": "Lock repositories and revoke tokens", "allowed_tools": ["lock_repo", "revoke_tokens"]}, {"agent_id": "release_manager", "agent_title": "DevOps Agent", "role": "Rollback production to safe version", "allowed_tools": ["rollback"]}, {"agent_id": "comms", "agent_title": "Communications Agent", "role": "Email CTO and alert engineering on Slack", "allowed_tools": ["send_email", "send_slack"]}], "scenario": "Security incident response with lockdown and rollback"}

User: "New developer Alice starts Monday, send offer and set up access"
{"plan": [{"agent_id": "recruitment", "agent_title": "HR Agent", "role": "Send offer confirmation email and grant GitHub access", "allowed_tools": ["send_email", "grant_access"]}, {"agent_id": "comms", "agent_title": "Communications Agent", "role": "Welcome message on Slack", "allowed_tools": ["send_slack"]}], "scenario": "New employee onboarding"}

User: "Deploy v3.0 and announce the launch"
{"plan": [{"agent_id": "release_manager", "agent_title": "DevOps Agent", "role": "Deploy v3.0 to production", "allowed_tools": ["deploy"]}, {"agent_id": "opensource", "agent_title": "Open Source Agent", "role": "Create GitHub release", "allowed_tools": ["create_release"]}, {"agent_id": "comms", "agent_title": "Communications Agent", "role": "Send launch announcement", "allowed_tools": ["send_email", "send_slack"]}], "scenario": "Product launch with deployment and announcement"}

Now respond to the user's request:"""


@router.post("/orchestrate")
async def orchestrate(
    req: OrchestrateRequest,
    workspace: Workspace = Depends(get_current_workspace),
):
    """AI-powered workflow planner: decides which agents to use and in what order."""
    from api.services.agent_chat import _PROVIDER_CONFIG
    provider, api_key = _resolve_ai_credentials(workspace)

    pconfig = _PROVIDER_CONFIG.get(provider, _PROVIDER_CONFIG.get("gemini", {}))
    if pconfig.get("type") != "openai":
        raise HTTPException(400, "Orchestrator requires OpenAI-compatible provider")

    from openai import OpenAI
    client = OpenAI(api_key=api_key or "ollama", base_url=pconfig["base_url"], timeout=30)

    import re as _re

    def _parse_plan(text: str) -> dict:
        """Extract JSON from LLM response — handles markdown, analysis tags, extra text."""
        text = text.strip()
        # Strip <analysis>...</analysis> thinking block (Claude Code pattern)
        import re as _re_inner
        text = _re_inner.sub(r"<analysis>[\s\S]*?</analysis>", "", text).strip()
        # Strip markdown code blocks
        if "```" in text:
            match = _re.search(r"```(?:json)?\s*\n?(.*?)```", text, _re.DOTALL)
            if match:
                text = match.group(1).strip()
        # Find first { ... } block
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object found in response")
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{": depth += 1
            elif text[i] == "}": depth -= 1
            if depth == 0:
                return json.loads(text[start:i+1])
        return json.loads(text[start:])

    # Try up to 2 times (retry on parse failure)
    last_error = None
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=pconfig["model"],
                messages=[
                    {"role": "system", "content": ORCHESTRATOR_PROMPT},
                    {"role": "user", "content": req.message},
                ],
                temperature=0.2 if attempt == 0 else 0.1,
                response_format={"type": "json_object"},  # Structured output
            )

            text = resp.choices[0].message.content or "{}"
            data = _parse_plan(text)
            plan = [OrchestrateStep(**s) for s in data.get("plan", [])]
            scenario = data.get("scenario", req.message)

            if not plan:
                # Fallback: use expense agent for vague requests
                plan = [OrchestrateStep(agent_id="expense", agent_title="E-Commerce Agent", role="Handle the request", allowed_tools=["process_refund", "notify_slack"])]
                scenario = req.message

            return OrchestrateResponse(plan=plan, scenario=scenario)

        except Exception as e:
            last_error = e
            logging.getLogger(__name__).warning(f"Orchestrate attempt {attempt+1} failed: {e}")

    raise HTTPException(500, f"Planning failed after 2 attempts: {str(last_error)[:200]}")


class SubAgentRequest(BaseModel):
    role: str  # "risk_assessor" | "validator" | "summary"
    context: str


SUB_AGENT_PROMPTS = {
    "risk_assessor": """You are a Risk Assessment Agent. You are being briefed on a workflow that is ABOUT TO execute — your assessment determines whether additional guardrails are needed.

For each step, evaluate:
- Financial risk (amounts involved, budget impact)
- Security risk (external communications, access changes, credential operations)
- Compliance risk (GDPR, HIPAA, regulatory)
- Blast radius (how many people/systems affected)

Risk level thresholds:
- LOW: <$100 total, internal only, no credential changes
- MEDIUM: $100-$999, external emails, single system access changes
- HIGH: $1,000-$9,999, multiple external parties, credential rotation, bulk operations
- CRITICAL: $10,000+, mass operations (10+ users), all-system access changes, irreversible actions

Respond in this EXACT format:
RISK LEVEL: LOW/MEDIUM/HIGH/CRITICAL
TOTAL ESTIMATED SPEND: $X
FLAGS:
- [flag 1]
- [flag 2]
RECOMMENDATION: [one sentence]

Be concise. Max 6 lines.""",

    "validator": """You are a Validation Agent. A workflow step just completed — you are an independent reviewer. Your job is not to confirm it works — it's to try to BREAK it.

Validate (standard checks):
- Did the amount match the request? (e.g., asked for $420, charged $420?)
- Is the connection correct? (e.g., stripe for payments, gmail for emails?)
- Are there duplicate actions? (same tool called twice with same params?)
- Any obvious errors in the results?

Adversarial probes (try to find anomalies):
- Amount anomaly: Is the total spend unusually high for this type of request?
- Scope creep: Did the agent do MORE than what was asked?
- Target mismatch: Are emails/payments going to the correct recipients?
- Sequence violation: Were actions executed in the wrong order?

Respond in this EXACT format:
STATUS: PASS/WARN/FAIL
CHECKS:
- [check]: [result]
ADVERSARIAL PROBE: [what you tested + result]
VALIDATED: X/Y actions passed

Be concise. Max 7 lines.""",

    "cost_estimator": """You are a Cost Estimation Agent. You are reviewing costs BEFORE the workflow runs — your estimate helps the approver decide whether to authorize the spend.

For each step, estimate:
- Direct cost (payment amounts, charges)
- Which costs will need approval (based on thresholds: <$100 auto, $100-$499 manager, $500+ CFO)
- Total estimated spend

Respond in this EXACT format:
TOTAL ESTIMATED COST: $X
BREAKDOWN:
- Step 1: $X (auto/manager/CFO approval)
- Step 2: $0 (no cost)
APPROVAL NEEDED: X of Y steps require human approval
BUDGET IMPACT: [one sentence]

Be concise. Max 6 lines.""",

    "compliance_checker": """You are a Compliance Agent. You are reviewing a planned workflow BEFORE execution. Your flags may block or modify actions — be precise about which regulations apply and why.

Check for:
- GDPR: Does any action involve EU personal data? Email to external parties?
- PCI-DSS: Payment card data handling?
- HIPAA: Medical/health data?
- PII Exposure: Names, emails, financial data in Slack messages or emails?
- Data Residency: Cross-border data transfers?

Respond in this EXACT format:
COMPLIANCE STATUS: CLEAR/WARNING/VIOLATION
FLAGS:
- [flag or "No compliance issues found"]
REGULATIONS: [which regulations apply]
RECOMMENDATION: [one sentence]

Be concise. Max 6 lines.""",

    "rollback_planner": """You are a Rollback Planning Agent. You are creating a safety net BEFORE the workflow executes — if any step fails, operators will follow your plan to undo damage.

For each step, define:
- What to undo if this step fails
- Dependencies (which previous steps need reversal)
- Priority (critical/standard)

Respond in this EXACT format:
ROLLBACK PLAN:
- Step 1 fails: [action to undo]
- Step 2 fails: [action to undo + cascade]
- Step 3 fails: [action to undo + cascade]
CRITICAL DEPENDENCIES: [which steps can't be undone]

Be concise. Max 6 lines.""",

    "audit_reporter": """You are an Audit Report Agent. The workflow is complete — you are generating the official compliance-ready audit trail that will be stored for SOC2/regulatory review.

Include for each action:
- Timestamp (relative: T+0s, T+5s, etc.)
- Agent that performed it
- Action and connection
- Status (approved/pending/blocked)
- Rule that triggered (if any)
- Risk level

Respond in this EXACT format:
AUDIT TRAIL:
[T+0s] Agent: action → status (rule: X)
[T+Xs] Agent: action → status
TOTAL ACTIONS: X | APPROVED: X | PENDING: X | BLOCKED: X
COMPLIANCE: [one sentence assessment]

Be concise. Max 8 lines.""",

    "summary": """You are a Summary Agent. The entire workflow has finished — you are writing an executive brief for the human operator who approved (or will review) these actions.

Use this structured format:
REQUEST: [one-line what was asked]
ACTIONS TAKEN:
- [action] → [status: approved/pending/blocked] via [connection]
FINANCIAL IMPACT: $X total ($X auto-approved, $X pending approval, $X blocked)
SECURITY: [credential isolation status — all via Token Vault? any anomalies?]
PENDING: [what still needs human approval]
NEXT STEPS: [1-2 recommended follow-up actions]

Be concise. Max 8 lines.""",
}


@router.post("/sub-agent")
async def run_sub_agent(
    req: SubAgentRequest,
    workspace: Workspace = Depends(get_current_workspace),
):
    """Run a specialized sub-agent (risk assessor, validator, or summary)."""
    from api.services.agent_chat import _PROVIDER_CONFIG
    provider, api_key = _resolve_ai_credentials(workspace)
    pconfig = _PROVIDER_CONFIG.get(provider, _PROVIDER_CONFIG.get("gemini", {}))

    if req.role not in SUB_AGENT_PROMPTS:
        raise HTTPException(400, f"Unknown sub-agent role: {req.role}")

    from openai import OpenAI
    client = OpenAI(api_key=api_key or "ollama", base_url=pconfig["base_url"], timeout=20)

    try:
        resp = client.chat.completions.create(
            model=pconfig["model"],
            messages=[
                {"role": "system", "content": SUB_AGENT_PROMPTS[req.role]},
                {"role": "user", "content": req.context},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        return {"role": req.role, "analysis": resp.choices[0].message.content or "No analysis."}
    except Exception as e:
        return {"role": req.role, "analysis": f"Analysis unavailable: {str(e)[:100]}"}


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
