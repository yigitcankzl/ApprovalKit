from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    job_id: str
    approver_id: str | None
    approver_name: str | None
    event_type: str
    action: str
    connection: str
    binding_message: str | None
    modified_params: dict | None
    note: str | None
    created_at: str

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_actions_week: int
    approved: int
    rejected: int
    blocked: int
    timed_out: int
    active_pre_approvals: int
    active_delegations: int
    ciba_usage: int
    ciba_limit: int
    scope_creep_alerts: int
