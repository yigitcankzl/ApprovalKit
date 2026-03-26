from typing import Any
from pydantic import BaseModel, Field, field_validator

from api.constants import FORBIDDEN_PARAM_KEYS


class ApprovalRequest(BaseModel):
    connection: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^[a-z][a-z0-9_:]*$")
    params: dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=200)

    @field_validator("params")
    @classmethod
    def no_system_keys(cls, v: dict) -> dict:
        if FORBIDDEN_PARAM_KEYS.intersection(v.keys()):
            raise ValueError("forbidden param key detected")
        return v


class ApprovalResponse(BaseModel):
    job_id: str
    status: str
    message: str | None = None
    risk: dict | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    approvals_count: int = 0
    required_count: int = 1
    final_params: dict | None = None
    completed_at: str | None = None
    execution_receipt: dict | None = None
