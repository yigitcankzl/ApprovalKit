from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.services.staff_service import StaffService
from backend.schemas.staff import AccessRequestCreate, DelegationCreate

router = APIRouter(prefix="/api/staff", tags=["staff"])


@router.get("/doctors")
async def list_doctors(specialty: str | None = None, db: AsyncSession = Depends(get_db)):
    doctors = await StaffService.get_doctors(db, specialty=specialty)
    return [
        {
            "id": str(d.id), "npi": d.npi,
            "first_name": d.first_name, "last_name": d.last_name,
            "email": d.email, "phone": d.phone,
            "specialty": d.specialty, "department": d.department,
            "is_cmo": d.is_cmo, "is_active": d.is_active,
            "on_vacation": d.on_vacation,
            "delegate_to_id": str(d.delegate_to_id) if d.delegate_to_id else None,
            "delegate_name": f"Dr. {d.delegate.first_name} {d.delegate.last_name}" if d.delegate else None,
            "delegate_until": d.delegate_until.isoformat() if d.delegate_until else None,
        }
        for d in doctors
    ]


@router.get("/members")
async def list_staff(role: str | None = None, db: AsyncSession = Depends(get_db)):
    staff = await StaffService.get_staff(db, role=role)
    return [
        {
            "id": str(s.id), "employee_id": s.employee_id,
            "first_name": s.first_name, "last_name": s.last_name,
            "email": s.email, "phone": s.phone,
            "role": s.role, "department": s.department,
            "access_level": s.access_level, "is_active": s.is_active,
        }
        for s in staff
    ]


@router.post("/access-request")
async def request_access_change(data: AccessRequestCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await StaffService.request_access_change(db, data.model_dump())
        req = result["request"]
        return {
            "id": str(req.id),
            "current_level": req.current_access_level,
            "requested_level": req.requested_access_level,
            "approval_status": result["approval_status"],
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/doctors/{doctor_id}/delegate")
async def set_delegation(doctor_id: str, data: DelegationCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await StaffService.set_delegation(db, doctor_id, data.model_dump())
        return {
            "doctor": f"Dr. {result['doctor'].first_name} {result['doctor'].last_name}",
            "delegate": f"Dr. {result['delegate'].first_name} {result['delegate'].last_name}",
            "until": result["delegation_until"],
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/doctors/{doctor_id}/delegate")
async def clear_delegation(doctor_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await StaffService.clear_delegation(db, doctor_id)
        return {"doctor": f"Dr. {result['doctor'].first_name} {result['doctor'].last_name}", "delegation": "cleared"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/shifts")
async def list_shifts(doctor_id: str | None = None, limit: int = 60, db: AsyncSession = Depends(get_db)):
    shifts = await StaffService.get_shifts(db, doctor_id=doctor_id, limit=limit)
    return [
        {
            "id": str(s.id),
            "doctor_id": str(s.doctor_id),
            "doctor_name": f"Dr. {s.doctor.first_name} {s.doctor.last_name}" if s.doctor else None,
            "shift_date": s.shift_date.isoformat(),
            "start_time": s.start_time.isoformat(),
            "end_time": s.end_time.isoformat(),
            "department": s.department,
            "status": s.status,
            "delegated_to": f"Dr. {s.delegated_to.first_name} {s.delegated_to.last_name}" if s.delegated_to else None,
        }
        for s in shifts
    ]
