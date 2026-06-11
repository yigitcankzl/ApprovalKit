"""Local action executor.

The local provider is built for *client* execution mode — the caller (the
SDK) runs the approved action itself, so there is normally nothing to
execute server-side. This executor exists only so the factory can return a
valid ``ActionExecutor`` when someone explicitly asks for server execution
without Auth0. It performs no side effects and never requires credentials;
it returns a skipped receipt so callers can tell nothing ran server-side.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from api.providers.base import ActionExecutionRequest, ActionExecutor


class LocalActionExecutor(ActionExecutor):
    name = "local-noop"

    async def execute(self, request: ActionExecutionRequest) -> dict[str, Any]:
        logger.info(
            "Local executor: no server-side execution for "
            f"{request.connection}/{request.action} — use execution_mode='client' "
            "to run the action in your own code."
        )
        return {
            "success": False,
            "skipped": True,
            "reason": "local provider has no server-side executor — use client execution mode",
            "connection": request.connection,
            "action": request.action,
        }
