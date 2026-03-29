from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.services.billing_service import BillingService
from backend.schemas.billing import BillingCreate, AppealCreate

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _bill_dict(b):
    return {
        "id": str(b.id), "invoice_number": b.invoice_number,
        "patient_id": str(b.patient_id),
        "patient_name": f"{b.patient.first_name} {b.patient.last_name}" if b.patient else None,
        "description": b.description, "procedure_code": b.procedure_code,
        "amount": float(b.amount),
        "insurance_covered": float(b.insurance_covered),
        "patient_responsibility": float(b.patient_responsibility),
        "status": b.status,
        "approval_job_id": b.approval_job_id,
        "appeal_status": b.appeal_status,
        "created_at": b.created_at.isoformat(),
    }


@router.get("")
async def list_billing(patient_id: str | None = None, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    records = await BillingService.get_billing_records(db, patient_id=patient_id, limit=limit, offset=offset)
    return [_bill_dict(b) for b in records]


@router.post("")
async def create_billing(data: BillingCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await BillingService.create_billing(db, data.model_dump())
        bill = result["billing"]
        return {
            "id": str(bill.id),
            "invoice_number": bill.invoice_number,
            "amount": float(bill.amount),
            "approval_status": result["approval_status"],
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{billing_id}/appeal")
async def file_appeal(billing_id: str, data: AppealCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await BillingService.file_appeal(db, billing_id, data.model_dump())
        return {
            "id": str(result["billing"].id),
            "appeal_status": result["appeal_status"],
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/stats")
async def billing_stats(db: AsyncSession = Depends(get_db)):
    return await BillingService.get_billing_stats(db)
