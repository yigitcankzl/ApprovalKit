from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.services.emergency_service import EmergencyService
from backend.schemas.emergency import EmergencyAccessCreate, SecurityBreachCreate

router = APIRouter(prefix="/api/emergency", tags=["emergency"])


def _event_dict(e):
    return {
        "id": str(e.id), "event_type": e.event_type,
        "severity": e.severity,
        "patient_id": str(e.patient_id) if e.patient_id else None,
        "patient_name": f"{e.patient.first_name} {e.patient.last_name}" if e.patient else None,
        "triggered_by": e.triggered_by,
        "reason": e.reason, "status": e.status,
        "approval_job_id": e.approval_job_id,
        "auto_timeout_seconds": e.auto_timeout_seconds,
        "actions_taken": e.actions_taken,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "resolved_by": e.resolved_by,
        "created_at": e.created_at.isoformat(),
    }


@router.get("/events")
async def list_emergencies(limit: int = 50, db: AsyncSession = Depends(get_db)):
    events = await EmergencyService.get_all_emergencies(db, limit=limit)
    return [_event_dict(e) for e in events]


@router.get("/active")
async def active_emergencies(db: AsyncSession = Depends(get_db)):
    events = await EmergencyService.get_active_emergencies(db)
    return [_event_dict(e) for e in events]


@router.post("/data-access")
async def emergency_data_access(data: EmergencyAccessCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await EmergencyService.request_emergency_access(db, data.model_dump())
        return _event_dict(result["emergency"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/security-breach")
async def report_security_breach(data: SecurityBreachCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await EmergencyService.report_security_breach(db, data.model_dump())
        return _event_dict(result["emergency"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{event_id}/resolve")
async def resolve_emergency(event_id: str, resolved_by: str = "admin", db: AsyncSession = Depends(get_db)):
    try:
        result = await EmergencyService.resolve_emergency(db, event_id, resolved_by)
        return _event_dict(result["emergency"])
    except ValueError as e:
        raise HTTPException(400, str(e))
