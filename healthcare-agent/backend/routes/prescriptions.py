import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db, async_session
from backend.services.prescription_service import PrescriptionService
from backend.schemas.prescription import PrescriptionCreate, DoseChangeCreate

logger = logging.getLogger("healthcare.prescriptions")

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])


def _rx_dict(rx):
    return {
        "id": str(rx.id), "rx_number": rx.rx_number,
        "patient_id": str(rx.patient_id),
        "patient_name": f"{rx.patient.first_name} {rx.patient.last_name}" if rx.patient else None,
        "prescribing_doctor_id": str(rx.prescribing_doctor_id),
        "doctor_name": f"Dr. {rx.prescribing_doctor.first_name} {rx.prescribing_doctor.last_name}" if rx.prescribing_doctor else None,
        "medication_name": rx.medication_name, "medication_code": rx.medication_code,
        "dosage": rx.dosage, "frequency": rx.frequency,
        "quantity": rx.quantity, "refills": rx.refills,
        "is_controlled": rx.is_controlled, "schedule_class": rx.schedule_class,
        "status": rx.status,
        "approved_by_doctor": rx.approved_by_doctor,
        "approved_by_pharmacist": rx.approved_by_pharmacist,
        "approved_by_cmo": rx.approved_by_cmo,
        "approval_job_id": rx.approval_job_id,
        "created_at": rx.created_at.isoformat(),
    }


@router.get("")
async def list_prescriptions(patient_id: str | None = None, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    prescriptions = await PrescriptionService.get_prescriptions(db, patient_id=patient_id, limit=limit, offset=offset)
    return [_rx_dict(rx) for rx in prescriptions]


async def _process_approval_in_background(rx_id: str, data: dict):
    """Run the blocking ApprovalKit gate in background so HTTP responds immediately."""
    try:
        async with async_session() as db:
            result = await PrescriptionService.create_prescription(db, data, rx_id=rx_id)
            logger.info(f"Background approval for {rx_id}: {result['approval_status']}")
    except Exception as e:
        logger.error(f"Background approval failed for {rx_id}: {e}")


@router.post("")
async def create_prescription(data: PrescriptionCreate, bg: BackgroundTasks = BackgroundTasks(), db: AsyncSession = Depends(get_db)):
    try:
        # Step 1: Create prescription record immediately (pending_approval)
        result = await PrescriptionService.create_prescription_record(db, data.model_dump())
        rx = result["prescription"]

        # Step 2: Run approval in background (non-blocking)
        bg.add_task(_process_approval_in_background, str(rx.id), data.model_dump())

        return {
            "id": str(rx.id),
            "rx_number": rx.rx_number,
            "approval_status": "pending_approval",
            "medication": rx.medication_name,
            "dosage": rx.dosage,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/dose-change")
async def request_dose_change(data: DoseChangeCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await PrescriptionService.request_dose_change(db, data.model_dump())
        dc = result["dose_change"]
        return {
            "id": str(dc.id),
            "prescription_id": str(dc.prescription_id),
            "previous_dosage": dc.previous_dosage,
            "new_dosage": dc.new_dosage,
            "approval_status": result["approval_status"],
            "is_first_change": dc.is_first_change,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{prescription_id}")
async def get_prescription(prescription_id: str, db: AsyncSession = Depends(get_db)):
    rx = await PrescriptionService.get_prescription(db, prescription_id)
    if not rx:
        raise HTTPException(404, "Prescription not found")
    return _rx_dict(rx)
