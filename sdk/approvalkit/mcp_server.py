"""
ApprovalKit MCP Server
======================
Exposes ApprovalKit as a Model Context Protocol (MCP) tool server.

Any MCP-compatible AI agent (Claude, GPT, etc.) can use these tools
to request approvals, check status, and list connections — all through
the standard MCP protocol.

Usage:
    # stdio transport (default for Claude Desktop)
    python mcp_server.py

    # Or add to Claude Desktop config:
    # {
    #   "mcpServers": {
    #     "approvalkit": {
    #       "command": "python",
    #       "args": ["mcp_server.py"],
    #       "env": {
    #         "APPROVALKIT_URL": "http://localhost:8000",
    #         "APPROVALKIT_API_KEY": "ak_...",
    #         "APPROVALKIT_HMAC_SECRET": "..."
    #       }
    #     }
    #   }
    # }
"""
import hashlib
import hmac
import json
import os
import time
from typing import Any

import httpx

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "MCP SDK not installed. Run: pip install mcp\n"
        "See: https://github.com/modelcontextprotocol/python-sdk"
    )

# Config from environment
BASE_URL = os.environ.get("APPROVALKIT_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("APPROVALKIT_API_KEY", "")
HMAC_SECRET = os.environ.get("APPROVALKIT_HMAC_SECRET", "")

mcp = FastMCP(
    "ApprovalKit",
    description="Human approval middleware for AI agents. Request approval before executing high-stakes actions.",
)


def _sign(body: str) -> tuple[str, str]:
    """HMAC-SHA256 request signing."""
    ts = str(int(time.time()))
    sign_key = HMAC_SECRET
    if API_KEY:
        sign_key = f"{HMAC_SECRET}:{API_KEY}"
    sig = hmac.new(sign_key.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    return ts, sig


def _headers(ts: str, sig: str) -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "X-Signature": f"hmac-sha256={ts}.{sig}",
        "Content-Type": "application/json",
    }


async def _api_call(method: str, path: str, body: dict | None = None) -> dict:
    """Make an authenticated API call to ApprovalKit."""
    body_str = json.dumps(body, separators=(",", ":")) if body else ""
    ts, sig = _sign(body_str)
    async with httpx.AsyncClient(timeout=30) as client:
        if method == "GET":
            r = await client.get(f"{BASE_URL}{path}", headers=_headers(ts, sig))
        else:
            r = await client.post(f"{BASE_URL}{path}", content=body_str, headers=_headers(ts, sig))
        return r.json()


@mcp.tool()
async def request_approval(
    connection: str,
    action: str,
    params: dict[str, Any],
    user_id: str = "mcp-agent",
) -> str:
    """Request human approval for an action. The action will NOT execute until a human approves it.

    Args:
        connection: Service connection slug (e.g. "stripe-prod", "github-main", "slack")
        action: Action to perform (e.g. "charge", "deploy", "send_message")
        params: Action parameters (e.g. {"amount": 500, "customer": "alice@example.com"})
        user_id: Identifier for this agent (for audit trail)

    Returns:
        Approval status and job ID. Poll with check_approval_status() to wait for the decision.
    """
    import uuid
    result = await _api_call("POST", "/api/v1/request", {
        "connection": connection,
        "action": action,
        "params": params,
        "user_id": user_id,
        "idempotency_key": str(uuid.uuid4()),
    })
    return json.dumps(result, indent=2)


@mcp.tool()
async def check_approval_status(job_id: str) -> str:
    """Check the status of a pending approval request.

    Args:
        job_id: The job ID returned by request_approval()

    Returns:
        Current status: pending, approved, rejected, timeout, or blocked.
        If approved, includes final_params (may differ from original if approver modified them).
    """
    ts, sig = _sign("")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{BASE_URL}/api/v1/status/{job_id}",
            headers=_headers(ts, sig),
        )
        return json.dumps(r.json(), indent=2)


@mcp.tool()
async def wait_for_approval(
    connection: str,
    action: str,
    params: dict[str, Any],
    user_id: str = "mcp-agent",
    timeout_seconds: int = 300,
) -> str:
    """Request approval and wait until it's granted or denied. Blocks until resolution.

    This is a convenience tool that combines request_approval + polling.
    Use this when you want to wait for the human's decision before proceeding.

    Args:
        connection: Service connection slug
        action: Action to perform
        params: Action parameters
        user_id: Agent identifier
        timeout_seconds: Max seconds to wait (default 300)

    Returns:
        Final result: approved (with execution result) or rejected/timeout/blocked.
    """
    import uuid
    result = await _api_call("POST", "/api/v1/request", {
        "connection": connection,
        "action": action,
        "params": params,
        "user_id": user_id,
        "idempotency_key": str(uuid.uuid4()),
    })

    status = result.get("status")
    if status in ("approved", "pre_approved"):
        return json.dumps({"status": status, "message": "Pre-approved, action executed."}, indent=2)
    if status == "blocked":
        return json.dumps({"status": "blocked", "message": result.get("message", "Blocked by policy")}, indent=2)

    job_id = result.get("job_id")
    if not job_id:
        return json.dumps(result, indent=2)

    # Poll for decision
    import asyncio
    deadline = time.time() + timeout_seconds
    interval = 3
    while time.time() < deadline:
        ts, sig = _sign("")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BASE_URL}/api/v1/status/{job_id}", headers=_headers(ts, sig))
            data = r.json()
            s = data.get("status", "pending")
            if s in ("approved", "rejected", "timeout", "blocked"):
                return json.dumps(data, indent=2)
        await asyncio.sleep(interval)
        interval = min(interval * 1.5, 15)

    return json.dumps({"status": "timeout", "job_id": job_id, "message": "Approval timed out"}, indent=2)


@mcp.tool()
async def list_connections() -> str:
    """List all available service connections and their supported actions.

    Returns a list of connections with their slugs, actions, and connection status.
    Use the slug and action values in request_approval().
    """
    ts, sig = _sign("")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE_URL}/api/v1/connections", headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        })
        connections = r.json()
        summary = []
        for c in connections:
            summary.append({
                "slug": c["slug"],
                "name": c["name"],
                "service": c["service"],
                "actions": c["actions"],
                "connected": c.get("has_credentials", False),
            })
        return json.dumps(summary, indent=2)


@mcp.tool()
async def list_rules() -> str:
    """List all active approval rules. Shows what actions need approval and what's auto-approved.

    Returns rules with their conditions, approval model, and approver count.
    """
    ts, sig = _sign("")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE_URL}/api/v1/rules", headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        })
        return json.dumps(r.json(), indent=2)


@mcp.resource("approvalkit://config")
async def get_config() -> str:
    """Current ApprovalKit configuration — base URL, connected services, active rules."""
    return json.dumps({
        "base_url": BASE_URL,
        "api_key_preview": f"{API_KEY[:8]}...{API_KEY[-4:]}" if len(API_KEY) > 12 else "not set",
        "hmac_configured": bool(HMAC_SECRET),
    }, indent=2)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
