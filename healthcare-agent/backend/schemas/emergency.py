from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class EmergencyAccessCreate(BaseModel):
    patient_id: str
    triggered_by: str
    reason: str


class SecurityBreachCreate(BaseModel):
    patient_id: Optional[str] = None
    triggered_by: str
    reason: str
    severity: str = "critical"


class EmergencyResponse(BaseModel):
    id: str
    event_type: str
    severity: str
    patient_id: Optional[str]
    triggered_by: str
    reason: str
    status: str
    approval_job_id: Optional[str]
    auto_timeout_seconds: int
    actions_taken: Optional[str]
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
