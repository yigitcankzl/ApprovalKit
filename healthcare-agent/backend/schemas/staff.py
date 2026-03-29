from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class AccessRequestCreate(BaseModel):
    staff_id: str
    requested_access_level: str
    reason: str


class DelegationCreate(BaseModel):
    delegate_to_id: str
    days: int = 14
    reason: str = ""


class StaffResponse(BaseModel):
    id: str
    employee_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    role: str
    department: str
    access_level: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DoctorResponse(BaseModel):
    id: str
    npi: str
    first_name: str
    last_name: str
    email: str
    phone: str
    specialty: str
    department: str
    license_number: str
    is_cmo: bool
    is_active: bool
    on_vacation: bool
    delegate_to_id: Optional[str]
    delegate_until: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
