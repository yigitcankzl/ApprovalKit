from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class PrescriptionCreate(BaseModel):
    patient_id: str
    prescribing_doctor_id: str
    medication_name: str
    medication_code: str = ""
    dosage: str
    frequency: str = "once daily"
    quantity: int = 30
    refills: int = 0
    is_controlled: bool = False
    schedule_class: Optional[str] = None
    pharmacy_email: str = "pharmacy@medcore-hospital.com"
    notes: Optional[str] = None


class PrescriptionResponse(BaseModel):
    id: str
    rx_number: str
    patient_id: str
    prescribing_doctor_id: str
    medication_name: str
    medication_code: str
    dosage: str
    frequency: str
    quantity: int
    refills: int
    is_controlled: bool
    schedule_class: Optional[str]
    status: str
    approval_job_id: Optional[str]
    approved_by_doctor: bool
    approved_by_pharmacist: bool
    approved_by_cmo: bool
    pharmacy_email: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DoseChangeCreate(BaseModel):
    prescription_id: str
    requested_by_doctor_id: str
    new_dosage: str
    reason: str


class DoseChangeResponse(BaseModel):
    id: str
    prescription_id: str
    patient_id: str
    requested_by_doctor_id: str
    previous_dosage: str
    new_dosage: str
    reason: str
    status: str
    approval_job_id: Optional[str]
    is_first_change: bool
    created_at: datetime

    class Config:
        from_attributes = True
