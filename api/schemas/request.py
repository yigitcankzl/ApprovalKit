from typing import Any
from pydantic import BaseModel, Field, field_validator

from api.constants import FORBIDDEN_PARAM_KEYS, EXECUTION_MODES, DEFAULT_EXECUTION_MODE


class ApprovalRequest(BaseModel):
    connection: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^[a-z][a-z0-9_:]*$")
    params: dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=200)
    # Who runs the approved action. Omitted on the wire → "server" (legacy
    # REST behavior). New SDKs send "client" so the caller runs the action.
    execution_mode: str = Field(default=DEFAULT_EXECUTION_MODE)

    @field_validator("params")
    @classmethod
    def no_system_keys(cls, v: dict) -> dict:
        if FORBIDDEN_PARAM_KEYS.intersection(v.keys()):
            raise ValueError("forbidden param key detected")
        return v

    @field_validator("execution_mode")
    @classmethod
    def valid_execution_mode(cls, v: str) -> str:
        if v not in EXECUTION_MODES:
            raise ValueError(
                f"execution_mode must be one of {sorted(EXECUTION_MODES)}, got {v!r}"
            )
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
    rejection_reason: str | None = None
    retry_allowed: bool = True
    risk_score: int = 0
    risk_level: str = "low"
    # Time-boxed: when the approved action expires if not executed
    approval_expires_at: str | None = None
    expires_at: str | None = None
