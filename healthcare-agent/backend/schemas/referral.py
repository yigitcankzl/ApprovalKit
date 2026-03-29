from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class ExternalReferralCreate(BaseModel):
    patient_id: str
    referring_doctor_id: str
    clinic_name: str
    clinic_email: str
    reason: str
    data_scope: str = "summary"


class InsuranceDataRequestCreate(BaseModel):
    patient_id: str
    insurance_provider_id: str
    requested_data_scope: str = "summary"
    reason: str


class ResearchExportCreate(BaseModel):
    referring_doctor_id: str
    research_entity_name: str
    research_entity_email: str
    reason: str
    patient_ids: list[str] = []
    patient_count: int = 0
    data_scope: str = "anonymized"


class ReferralResponse(BaseModel):
    id: str
    referral_type: str
    patient_id: str
    referring_doctor_id: str
    external_entity_name: str
    external_entity_email: str
    reason: str
    data_scope: str
    final_data_scope: Optional[str]
    shared_drive_link: Optional[str]
    patient_count: int
    status: str
    approval_job_id: Optional[str]
    audit_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
