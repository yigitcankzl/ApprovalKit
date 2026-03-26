import uuid
from datetime import datetime, time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.approver import Approver
from api.models.workspace import Workspace
from api.schemas.approver import ApproverCreate, ApproverUpdate, DelegationRequest, ApproverResponse
from api.middleware.workspace import get_current_workspace

settings = get_settings()

router = APIRouter(prefix="/api/v1/approvers", tags=["approvers"])


async def _resolve_workspace_id(
    workspace: Workspace = Depends(get_current_workspace),
) -> uuid.UUID:
    return workspace.id


def _approver_to_response(a: Approver) -> dict:
    return {
        "id": str(a.id),
        "name": a.name,
        "email": a.email,
        "auth0_user_id": a.auth0_user_id,
        "notify_channel": a.notify_channel or [],
        "urgent_channel": a.urgent_channel or [],
        "blackout_start": a.blackout_start.isoformat() if a.blackout_start else None,
        "blackout_end": a.blackout_end.isoformat() if a.blackout_end else None,
        "delegate_to": str(a.delegate_to) if a.delegate_to else None,
        "delegate_from": a.delegate_from.isoformat() if a.delegate_from else None,
        "delegate_until": a.delegate_until.isoformat() if a.delegate_until else None,
        "created_at": a.created_at.isoformat(),
    }


def _parse_time(t: str | None) -> time | None:
    if not t:
        return None
    parts = t.split(":")
    return time(int(parts[0]), int(parts[1]))


@router.post("", response_model=ApproverResponse)
async def create_approver(
    data: ApproverCreate,
    db: AsyncSession = Depends(get_db),
    ws_id: uuid.UUID = Depends(_resolve_workspace_id),
):
    approver = Approver(
        workspace_id=ws_id,
        name=data.name,
        email=data.email,
        auth0_user_id=data.auth0_user_id,
        notify_channel=data.notify_channel,
        urgent_channel=data.urgent_channel,
        blackout_start=_parse_time(data.blackout_start),
        blackout_end=_parse_time(data.blackout_end),
    )
    db.add(approver)
    await db.commit()
    await db.refresh(approver)
    return ApproverResponse(**_approver_to_response(approver))


@router.get("")
async def list_approvers(
    db: AsyncSession = Depends(get_db),
    ws_id: uuid.UUID = Depends(_resolve_workspace_id),
):
    result = await db.execute(
        select(Approver)
        .where(Approver.workspace_id == ws_id)
        .order_by(Approver.name)
    )
    approvers = result.scalars().all()
    return [_approver_to_response(a) for a in approvers]


@router.get("/link-callback")
async def link_callback(
    db: AsyncSession = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/approvers?error={error}")
    if not code or not state:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/approvers?error=missing_code")
    # State format: approver_id:workspace_id
    parts = state.split(":", 1) if state else []
    if len(parts) != 2:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/approvers?error=invalid_state")
    try:
        approver_uuid = uuid.UUID(parts[0])
        workspace_uuid = uuid.UUID(parts[1])
    except ValueError:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/approvers?error=invalid_state")

    result = await db.execute(select(Approver).where(Approver.id == approver_uuid, Approver.workspace_id == workspace_uuid))
    approver = result.scalar_one_or_none()
    if not approver:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/approvers?error=approver_not_found")

    callback_url = f"{settings.CALLBACK_BASE_URL}/api/v1/approvers/link-callback"
    web_client_id = settings.AUTH0_WEB_CLIENT_ID or settings.AUTH0_CLIENT_ID
    web_client_secret = settings.AUTH0_WEB_CLIENT_SECRET or settings.AUTH0_CLIENT_SECRET

    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            f"https://{settings.AUTH0_DOMAIN}/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": web_client_id,
                "client_secret": web_client_secret,
                "code": code,
                "redirect_uri": callback_url,
            },
        )
        if token_resp.status_code != 200:
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/approvers?error=token_exchange_failed")

        userinfo_resp = await client.get(
            f"https://{settings.AUTH0_DOMAIN}/userinfo",
            headers={"Authorization": f"Bearer {token_resp.json()['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/approvers?error=userinfo_failed")
        userinfo = userinfo_resp.json()

    approver.auth0_user_id = userinfo.get("sub")
    await db.commit()
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/approvers?linked={approver.name}")


@router.get("/{approver_id}/link-url")
async def get_link_url(approver_id: str, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id), Approver.workspace_id == ws.id))
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")

    callback_url = f"{settings.CALLBACK_BASE_URL}/api/v1/approvers/link-callback"
    client_id = settings.AUTH0_WEB_CLIENT_ID or settings.AUTH0_CLIENT_ID
    # State includes workspace_id for callback verification
    state_value = f"{approver_id}:{ws.id}"
    params = urlencode({
        "client_id": client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "state": state_value,
        "redirect_uri": callback_url,
    })
    return {"url": f"https://{settings.AUTH0_DOMAIN}/authorize?{params}"}


@router.get("/{approver_id}", response_model=ApproverResponse)
async def get_approver(approver_id: str, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id), Approver.workspace_id == ws.id))
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")
    return ApproverResponse(**_approver_to_response(approver))


@router.put("/{approver_id}", response_model=ApproverResponse)
async def update_approver(
    approver_id: str,
    data: ApproverUpdate,
    ws: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id), Approver.workspace_id == ws.id))
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")

    update_data = data.model_dump(exclude_unset=True)
    if "blackout_start" in update_data:
        update_data["blackout_start"] = _parse_time(update_data["blackout_start"])
    if "blackout_end" in update_data:
        update_data["blackout_end"] = _parse_time(update_data["blackout_end"])

    for key, value in update_data.items():
        setattr(approver, key, value)

    await db.commit()
    await db.refresh(approver)
    return ApproverResponse(**_approver_to_response(approver))


@router.delete("/{approver_id}", status_code=204)
async def delete_approver(approver_id: str, ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id), Approver.workspace_id == ws.id))
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")
    await db.delete(approver)
    await db.commit()


@router.put("/{approver_id}/delegate")
async def set_delegation(
    approver_id: str,
    data: DelegationRequest,
    ws: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id), Approver.workspace_id == ws.id))
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")

    delegate_result = await db.execute(select(Approver).where(Approver.id == data.delegate_to, Approver.workspace_id == ws.id))
    delegate = delegate_result.scalar_one_or_none()
    if not delegate:
        raise HTTPException(status_code=404, detail="Delegate approver not found in your workspace")

    approver.delegate_to = data.delegate_to
    approver.delegate_from = datetime.fromisoformat(data.delegate_from)
    approver.delegate_until = datetime.fromisoformat(data.delegate_until)

    await db.commit()
    return {"status": "delegation_set", "delegate_to": str(data.delegate_to)}


@router.delete("/{approver_id}/delegate")
async def remove_delegation(
    approver_id: str,
    ws: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id), Approver.workspace_id == ws.id))
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")

    approver.delegate_to = None
    approver.delegate_from = None
    approver.delegate_until = None

    await db.commit()
    return {"status": "delegation_removed"}
