import uuid
from pydantic import BaseModel, Field

from api.models.rule import ApprovalModel, TimeoutAction


class ConditionSchema(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    operator: str = Field(pattern=r"^(eq|ne|gt|gte|lt|lte|in|not_in|contains)$")
    value: str | int | float | bool | list


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    connection: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^[a-z][a-z0-9_:]*$")
    conditions: list[ConditionSchema] = Field(default_factory=list)
    model: ApprovalModel
    approver_ids: list[uuid.UUID] = Field(min_length=1)
    k_value: int | None = None
    timeout_seconds: int = Field(default=300, ge=30, le=3600)
    on_timeout: TimeoutAction = TimeoutAction.BLOCK
    escalate_to: uuid.UUID | None = None
    cooldown_max: int | None = Field(default=None, ge=1, le=1000)
    blackout_start: str | None = None
    blackout_end: str | None = None
    pre_approval: dict | None = None
    context_template: str | None = None
    partial_approval: bool = False
    quorum_window: int | None = Field(default=None, ge=30, le=7200)
    priority: int = Field(default=0, ge=0, le=100)


class RuleUpdate(BaseModel):
    name: str | None = None
    conditions: list[ConditionSchema] | None = None
    model: ApprovalModel | None = None
    approver_ids: list[uuid.UUID] | None = None
    k_value: int | None = None
    timeout_seconds: int | None = None
    on_timeout: TimeoutAction | None = None
    escalate_to: uuid.UUID | None = None
    cooldown_max: int | None = None
    blackout_start: str | None = None
    blackout_end: str | None = None
    pre_approval: dict | None = None
    context_template: str | None = None
    partial_approval: bool | None = None
    quorum_window: int | None = None
    priority: int | None = None
    is_active: bool | None = None


class RuleResponse(BaseModel):
    id: str
    name: str
    connection: str
    action: str
    conditions: list[dict]
    model: str
    approver_ids: list[str]
    k_value: int | None
    timeout_seconds: int
    on_timeout: str
    escalate_to: str | None
    cooldown_max: int | None
    blackout_start: str | None
    blackout_end: str | None
    pre_approval: dict | None
    context_template: str | None
    partial_approval: bool
    quorum_window: int | None
    priority: int
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
