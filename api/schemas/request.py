from typing import Any
from pydantic import BaseModel, Field, field_validator


class ApprovalRequest(BaseModel):
    connection: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^[a-z][a-z0-9_:]*$")
    params: dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(pattern=r"^auth0\|")
    idempotency_key: str = Field(min_length=1, max_length=200)

    @field_validator("params")
    @classmethod
    def no_system_keys(cls, v: dict) -> dict:
        forbidden = {"__proto__", "constructor", "$where", "__prototype__"}
        if forbidden.intersection(v.keys()):
            raise ValueError("forbidden param key detected")
        return v


class ApprovalResponse(BaseModel):
    job_id: str
    status: str
    message: str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    approvals_count: int = 0
    required_count: int = 1
    final_params: dict | None = None
    completed_at: str | None = None
