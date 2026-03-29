from datetime import date, datetime
from pydantic import BaseModel
from typing import Optional


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    phone: str
    email: str
    address: dict = {}
    emergency_contact: dict = {}
    blood_type: str = "O+"
    allergies: list[str] = []
    conditions: list[str] = []
    primary_doctor_id: Optional[str] = None
    insurance_id: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    notes: Optional[str] = None


class PatientResponse(BaseModel):
    id: str
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    ssn_masked: str
    phone: str
    email: str
    address: dict
    emergency_contact: dict
    blood_type: str
    allergies: list
    conditions: list
    medications_current: list
    primary_doctor_id: Optional[str]
    insurance_id: Optional[str]
    insurance_policy_number: Optional[str]
    status: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[dict] = None
    conditions: Optional[list[str]] = None
    allergies: Optional[list[str]] = None
    status: Optional[str] = None
    notes: Optional[str] = None
