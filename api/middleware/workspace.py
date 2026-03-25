"""
Per-user workspace resolution.

Every dashboard API call includes X-User-Sub header (Auth0 sub).
This middleware resolves the correct workspace for that user.

If user_sub is present but no workspace matches → 404 (new user, needs setup).
If no sub header → fallback to first workspace (SDK/API calls without auth).
"""
from fastapi import Depends, HTTPException, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.workspace import Workspace


async def get_current_workspace(request: Request, db: AsyncSession = Depends(get_db)) -> Workspace:
    """
    Resolve workspace for the current user.
    - X-User-Sub present → must match owner_auth0_sub (no fallback for logged-in users)
    - No header → fallback to first active workspace (backwards compat for SDK/API)
    """
    user_sub = request.headers.get("X-User-Sub", "").strip()
    logger.debug(f"Workspace resolve: sub={user_sub!r} path={request.url.path}")

    if user_sub:
        # Logged-in user: find THEIR workspace only
        result = await db.execute(
            select(Workspace).where(
                Workspace.owner_auth0_sub == user_sub,
                Workspace.is_active.is_(True),
            ).limit(1)
        )
        ws = result.scalar_one_or_none()
        if ws:
            return ws
        # No workspace for this user — they need to set up
        raise HTTPException(
            status_code=404,
            detail="No workspace found for your account. Complete setup at /settings first.",
        )

    # No auth header (SDK calls, API key auth, etc.) → fallback
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="No workspace configured. Complete setup first.")
    return ws
