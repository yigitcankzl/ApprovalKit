from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.services.referral_service import ReferralService
from backend.schemas.referral import ExternalReferralCreate, InsuranceDataRequestCreate, ResearchExportCreate

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


def _ref_dict(r):
    return {
        "id": str(r.id), "referral_type": r.referral_type,
        "patient_id": str(r.patient_id),
        "patient_name": f"{r.patient.first_name} {r.patient.last_name}" if r.patient else None,
        "referring_doctor_id": str(r.referring_doctor_id),
        "external_entity_name": r.external_entity_name,
        "external_entity_email": r.external_entity_email,
        "reason": r.reason,
        "data_scope": r.data_scope,
        "final_data_scope": r.final_data_scope,
        "shared_drive_link": r.shared_drive_link,
        "patient_count": r.patient_count,
        "status": r.status,
        "approval_job_id": r.approval_job_id,
        "audit_notes": r.audit_notes,
        "created_at": r.created_at.isoformat(),
    }


@router.get("")
async def list_referrals(referral_type: str | None = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    referrals = await ReferralService.get_referrals(db, referral_type=referral_type, limit=limit)
    return [_ref_dict(r) for r in referrals]


@router.post("/external")
async def create_external_referral(data: ExternalReferralCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await ReferralService.create_external_referral(db, data.model_dump())
        ref = result["referral"]
        return {
            "id": str(ref.id),
            "status": result["approval_status"],
            "data_scope": ref.data_scope,
            "shared_drive_link": ref.shared_drive_link,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/insurance-request")
async def create_insurance_request(data: InsuranceDataRequestCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await ReferralService.create_insurance_data_request(db, data.model_dump())
        req = result["request"]
        return {
            "id": str(req.id),
            "status": result["approval_status"],
            "requested_scope": req.requested_data_scope,
            "final_scope": req.final_data_scope,
            "partial_approval": result["partial_approval"],
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/research-export")
async def create_research_export(data: ResearchExportCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await ReferralService.create_research_export(db, data.model_dump())
        ref = result["referral"]
        return {
            "id": str(ref.id),
            "status": result["approval_status"],
            "patient_count": ref.patient_count,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
