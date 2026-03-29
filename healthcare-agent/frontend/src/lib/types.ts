export interface Patient {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  email: string;
  phone: string;
  blood_type: string;
  allergies: string[];
  conditions: string[];
  medications_current: string[];
  status: string;
  primary_doctor_id: string | null;
  primary_doctor: string | null;
  insurance: string | null;
  created_at: string;
}

export interface Prescription {
  id: string;
  rx_number: string;
  patient_id: string;
  patient_name: string | null;
  prescribing_doctor_id: string;
  doctor_name: string | null;
  medication_name: string;
  medication_code: string;
  dosage: string;
  frequency: string;
  quantity: number;
  refills: number;
  is_controlled: boolean;
  schedule_class: string | null;
  status: string;
  approved_by_doctor: boolean;
  approved_by_pharmacist: boolean;
  approved_by_cmo: boolean;
  approval_job_id: string | null;
  created_at: string;
}

export interface BillingRecord {
  id: string;
  invoice_number: string;
  patient_id: string;
  patient_name: string | null;
  description: string;
  procedure_code: string | null;
  amount: number;
  insurance_covered: number;
  patient_responsibility: number;
  status: string;
  approval_job_id: string | null;
  appeal_status: string | null;
  created_at: string;
}

export interface EmergencyEvent {
  id: string;
  event_type: string;
  severity: string;
  patient_id: string | null;
  patient_name: string | null;
  triggered_by: string;
  reason: string;
  status: string;
  approval_job_id: string | null;
  auto_timeout_seconds: number;
  actions_taken: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
}

export interface Doctor {
  id: string;
  npi: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  specialty: string;
  department: string;
  is_cmo: boolean;
  is_active: boolean;
  on_vacation: boolean;
  delegate_to_id: string | null;
  delegate_name: string | null;
  delegate_until: string | null;
}

export interface StaffMember {
  id: string;
  employee_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  role: string;
  department: string;
  access_level: string;
  is_active: boolean;
}

export interface Referral {
  id: string;
  referral_type: string;
  patient_id: string;
  patient_name: string | null;
  external_entity_name: string;
  reason: string;
  data_scope: string;
  final_data_scope: string | null;
  patient_count: number;
  status: string;
  approval_job_id: string | null;
  created_at: string;
}

export interface ActivityEvent {
  id: string;
  event_type: string;
  category: string;
  title: string;
  description: string;
  severity: string;
  entity_type: string | null;
  entity_id: string | null;
  approval_job_id: string | null;
  metadata: Record<string, any>;
  created_at: string;
}

export interface Scenario {
  id: string;
  title: string;
  description: string;
  category: string;
  approval_types: string[];
  steps: string[];
}

export interface DashboardStats {
  patients: { total: number; active: number };
  prescriptions: { pending_approval: number; approved: number; denied: number };
  emergencies: { active: number };
  appointments: { today: number };
  billing: { total_billed: number; pending: number };
  activity: { last_24h: number };
}
