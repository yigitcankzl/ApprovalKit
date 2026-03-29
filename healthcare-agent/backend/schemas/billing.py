from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class BillingCreate(BaseModel):
    patient_id: str
    description: str
    procedure_code: Optional[str] = None
    amount: float
    insurance_covered: float = 0
    patient_responsibility: float = 0
    notes: Optional[str] = None


class BillingResponse(BaseModel):
    id: str
    invoice_number: str
    patient_id: str
    description: str
    procedure_code: Optional[str]
    amount: float
    insurance_covered: float
    patient_responsibility: float
    status: str
    approval_job_id: Optional[str]
    approved_by: Optional[str]
    insurance_claim_id: Optional[str]
    appeal_status: Optional[str]
    appeal_job_id: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AppealCreate(BaseModel):
    reason: str
    doctor_id: str
