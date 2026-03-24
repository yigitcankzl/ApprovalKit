import uuid
from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.approver import Approver
from api.schemas.approver import ApproverCreate, ApproverUpdate, DelegationRequest, ApproverResponse

router = APIRouter(prefix="/api/v1/approvers", tags=["approvers"])


async def _resolve_workspace_id(
    workspace_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    if workspace_id:
        try:
            return uuid.UUID(workspace_id)
        except ValueError:
            pass
    from api.models.workspace import Workspace
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=500, detail="No active workspace found")
    return ws.id


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


@router.get("/{approver_id}", response_model=ApproverResponse)
async def get_approver(approver_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id)))
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")
    return ApproverResponse(**_approver_to_response(approver))


@router.put("/{approver_id}", response_model=ApproverResponse)
async def update_approver(
    approver_id: str,
    data: ApproverUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id)))
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


@router.put("/{approver_id}/delegate")
async def set_delegation(
    approver_id: str,
    data: DelegationRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id)))
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")

    delegate_result = await db.execute(select(Approver).where(Approver.id == data.delegate_to))
    delegate = delegate_result.scalar_one_or_none()
    if not delegate:
        raise HTTPException(status_code=404, detail="Delegate approver not found")

    approver.delegate_to = data.delegate_to
    approver.delegate_from = datetime.fromisoformat(data.delegate_from)
    approver.delegate_until = datetime.fromisoformat(data.delegate_until)

    await db.commit()
    return {"status": "delegation_set", "delegate_to": str(data.delegate_to)}


@router.delete("/{approver_id}/delegate")
async def remove_delegation(
    approver_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(approver_id)))
    approver = result.scalar_one_or_none()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")

    approver.delegate_to = None
    approver.delegate_from = None
    approver.delegate_until = None

    await db.commit()
    return {"status": "delegation_removed"}
