import uuid
from pydantic import BaseModel, Field

from api.models.rule import ApprovalModel, TimeoutAction


class ConditionSchema(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    operator: str = Field(pattern=r"^(eq|ne|gt|gte|lt|lte|in|not_in|contains|starts_with|ends_with|regex|between|exists|not_exists)$")
    value: str | int | float | bool | list


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    connection: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^[a-z][a-z0-9_:]*$")
    conditions: list[ConditionSchema] = Field(default_factory=list)
    model: ApprovalModel
    approver_ids: list[uuid.UUID] = Field(default_factory=list)
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
    step_up_model: ApprovalModel | None = None
    step_up_conditions: list[ConditionSchema] = Field(default_factory=list)
    approval_checklist: list[dict] | None = None  # [{"id": "amount", "label": "I verified the amount"}]
    max_requests_per_hour: int | None = Field(default=None, ge=1, le=10000)
    approval_expiry_seconds: int | None = Field(default=None, ge=60, le=86400)
    trigger_rules: list[dict] | None = None  # [{"connection": ..., "action": ..., "params": {...}}]
    on_approve_actions: list[dict] | None = None  # [{"connection": ..., "action": ..., "params": {...}}]


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
    step_up_model: ApprovalModel | None = None
    step_up_conditions: list[ConditionSchema] | None = None
    approval_checklist: list[dict] | None = None
    max_requests_per_hour: int | None = None
    approval_expiry_seconds: int | None = None
    trigger_rules: list[dict] | None = None
    on_approve_actions: list[dict] | None = None


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
    step_up_model: str | None = None
    step_up_conditions: list[dict] = []
    approval_checklist: list[dict] | None = None
    max_requests_per_hour: int | None = None
    approval_expiry_seconds: int | None = None
    trigger_rules: list[dict] | None = None
    on_approve_actions: list[dict] | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
