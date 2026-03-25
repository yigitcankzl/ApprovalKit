export type ApprovalModel = "any_one" | "specific" | "all_of_n" | "k_of_n" | "sequential";
export type TimeoutAction = "block" | "escalate";
export type JobState = "pending" | "ciba_sent" | "waiting_approval" | "partially_approved" | "approved" | "rejected" | "timeout" | "escalated" | "blocked" | "pre_approved";

export interface Condition {
  field: string;
  operator: string;
  value: string | number | boolean;
}

export interface Rule {
  id: string;
  name: string;
  connection: string;
  action: string;
  conditions: Condition[];
  model: ApprovalModel;
  approver_ids: string[];
  k_value: number | null;
  timeout_seconds: number;
  on_timeout: TimeoutAction;
  escalate_to: string | null;
  cooldown_max: number | null;
  blackout_start: string | null;
  blackout_end: string | null;
  pre_approval: any;
  context_template: string | null;
  partial_approval: boolean;
  quorum_window: number | null;
  priority: number;
  is_active: boolean;
  step_up_model: ApprovalModel | null;
  step_up_conditions: Condition[];
  created_at: string;
  updated_at: string;
}

export interface Approver {
  id: string;
  name: string;
  email: string;
  auth0_user_id: string;
  notify_channel: string[];
  urgent_channel: string[];
  blackout_start: string | null;
  blackout_end: string | null;
  delegate_to: string | null;
  delegate_from: string | null;
  delegate_until: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  job_id: string;
  approver_id: string | null;
  approver_name: string | null;
  event_type: string;
  action: string;
  connection: string;
  binding_message: string | null;
  modified_params: any;
  note: string | null;
  created_at: string;
}

export interface DashboardStats {
  total_actions_week: number;
  approved: number;
  rejected: number;
  blocked: number;
  timed_out: number;
  active_pre_approvals: number;
  active_delegations: number;
  ciba_usage: number;
  ciba_limit: number;
  scope_creep_alerts: number;
}
