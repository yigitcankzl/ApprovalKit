from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.services.patient_service import PatientService
from backend.schemas.patient import PatientCreate, PatientUpdate

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("")
async def list_patients(status: str | None = None, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    patients = await PatientService.get_patients(db, status=status, limit=limit, offset=offset)
    return [
        {
            "id": str(p.id), "mrn": p.mrn,
            "first_name": p.first_name, "last_name": p.last_name,
            "date_of_birth": p.date_of_birth.isoformat(),
            "gender": p.gender, "email": p.email, "phone": p.phone,
            "blood_type": p.blood_type, "allergies": p.allergies,
            "conditions": p.conditions, "medications_current": p.medications_current,
            "status": p.status,
            "primary_doctor_id": str(p.primary_doctor_id) if p.primary_doctor_id else None,
            "primary_doctor": f"Dr. {p.primary_doctor.first_name} {p.primary_doctor.last_name}" if p.primary_doctor else None,
            "insurance": p.insurance.name if p.insurance else None,
            "created_at": p.created_at.isoformat(),
        }
        for p in patients
    ]


@router.get("/{patient_id}")
async def get_patient(patient_id: str, db: AsyncSession = Depends(get_db)):
    patient = await PatientService.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    return {
        "id": str(patient.id), "mrn": patient.mrn,
        "first_name": patient.first_name, "last_name": patient.last_name,
        "date_of_birth": patient.date_of_birth.isoformat(),
        "gender": patient.gender, "ssn_masked": patient.ssn_masked,
        "email": patient.email, "phone": patient.phone,
        "address": patient.address, "emergency_contact": patient.emergency_contact,
        "blood_type": patient.blood_type, "allergies": patient.allergies,
        "conditions": patient.conditions, "medications_current": patient.medications_current,
        "status": patient.status, "notes": patient.notes,
        "primary_doctor_id": str(patient.primary_doctor_id) if patient.primary_doctor_id else None,
        "primary_doctor": f"Dr. {patient.primary_doctor.first_name} {patient.primary_doctor.last_name}" if patient.primary_doctor else None,
        "insurance_id": str(patient.insurance_id) if patient.insurance_id else None,
        "insurance": patient.insurance.name if patient.insurance else None,
        "insurance_policy_number": patient.insurance_policy_number,
        "created_at": patient.created_at.isoformat(),
    }


@router.post("")
async def register_patient(data: PatientCreate, db: AsyncSession = Depends(get_db)):
    result = await PatientService.register_patient(db, data.model_dump())
    patient = result["patient"]
    return {
        "id": str(patient.id),
        "mrn": result["mrn"],
        "name": f"{patient.first_name} {patient.last_name}",
        "onboarding": result["onboarding"],
    }


@router.put("/{patient_id}")
async def update_patient(patient_id: str, data: PatientUpdate, db: AsyncSession = Depends(get_db)):
    patient = await PatientService.update_patient(db, patient_id, data.model_dump(exclude_unset=True))
    if not patient:
        raise HTTPException(404, "Patient not found")
    return {"id": str(patient.id), "status": "updated"}


@router.get("/mrn/{mrn}")
async def get_patient_by_mrn(mrn: str, db: AsyncSession = Depends(get_db)):
    patient = await PatientService.get_patient_by_mrn(db, mrn)
    if not patient:
        raise HTTPException(404, "Patient not found")
    return {"id": str(patient.id), "mrn": patient.mrn, "name": f"{patient.first_name} {patient.last_name}"}
