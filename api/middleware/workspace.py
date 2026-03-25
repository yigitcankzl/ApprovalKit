"""
Per-user workspace resolution.

Every dashboard API call includes X-User-Sub header (Auth0 sub).
This middleware resolves the correct workspace for that user.

If no sub is provided, falls back to the first active workspace (backwards compat).
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.workspace import Workspace


async def get_current_workspace(request: Request, db: AsyncSession = Depends(get_db)) -> Workspace:
    """
    Resolve workspace for the current user.
    Priority:
      1. X-User-Sub header → workspace where owner_auth0_sub matches
      2. Fallback → first active workspace (single-tenant / dev mode)
    """
    user_sub = request.headers.get("X-User-Sub", "").strip()

    if user_sub:
        result = await db.execute(
            select(Workspace).where(
                Workspace.owner_auth0_sub == user_sub,
                Workspace.is_active.is_(True),
            ).limit(1)
        )
        ws = result.scalar_one_or_none()
        if ws:
            return ws

    # Fallback: first active workspace
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="No workspace configured. Complete setup first.")
    return ws
