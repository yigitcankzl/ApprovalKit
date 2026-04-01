import uuid
from pydantic import BaseModel, Field, EmailStr


class ApproverCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=1, max_length=320)
    auth0_user_id: str | None = Field(default=None, max_length=200)
    notify_channel: list[str] = Field(default=["guardian_push"])
    urgent_channel: list[str] = Field(default=["guardian_push", "email"])
    blackout_start: str | None = None
    blackout_end: str | None = None


class ApproverUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    notify_channel: list[str] | None = None
    urgent_channel: list[str] | None = None
    blackout_start: str | None = None
    blackout_end: str | None = None


class DelegationRequest(BaseModel):
    delegate_to: uuid.UUID
    delegate_from: str
    delegate_until: str


class ApproverResponse(BaseModel):
    id: str
    name: str
    email: str
    auth0_user_id: str | None
    notify_channel: list[str]
    urgent_channel: list[str]
    blackout_start: str | None
    blackout_end: str | None
    delegate_to: str | None
    delegate_from: str | None
    delegate_until: str | None
    created_at: str

    model_config = {"from_attributes": True}
