# Healthcare AI Agent — API Reference

Base URL: `http://localhost:3002`

## Patients

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/patients` | List patients (query: `status`, `limit`, `offset`) |
| GET | `/api/patients/{id}` | Get patient detail |
| POST | `/api/patients` | Register new patient (triggers onboarding) |
| PUT | `/api/patients/{id}` | Update patient |
| GET | `/api/patients/mrn/{mrn}` | Lookup by MRN |

### POST /api/patients
```json
{
  "first_name": "Maria",
  "last_name": "Garcia",
  "date_of_birth": "1985-03-15",
  "gender": "female",
  "phone": "(555) 234-5678",
  "email": "maria.garcia@email.com",
  "blood_type": "A+",
  "allergies": ["Penicillin"],
  "conditions": ["Type 2 Diabetes Mellitus"],
  "primary_doctor_id": "uuid-here",
  "insurance_id": "uuid-here"
}
```

**Onboarding triggers:**
1. Gmail → doctor notification (Token Vault)
2. Slack → #intake announcement (Token Vault)
3. Insurance verification (internal)
4. Google Calendar → first appointment (Token Vault)

## Prescriptions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/prescriptions` | List prescriptions (query: `patient_id`) |
| POST | `/api/prescriptions` | Create prescription (triggers approval) |
| POST | `/api/prescriptions/dose-change` | Request dose change |
| GET | `/api/prescriptions/{id}` | Get prescription detail |

### POST /api/prescriptions
```json
{
  "patient_id": "uuid",
  "prescribing_doctor_id": "uuid",
  "medication_name": "Metformin",
  "dosage": "500mg",
  "frequency": "twice daily",
  "quantity": 60,
  "is_controlled": false,
  "schedule_class": null
}
```

**Approval flow:**
- `is_controlled=false` → specific (doctor only)
- `is_controlled=true` → sequential (doctor → pharmacist)

### POST /api/prescriptions/dose-change
```json
{
  "prescription_id": "uuid",
  "requested_by_doctor_id": "uuid",
  "new_dosage": "1000mg",
  "reason": "Blood glucose not controlled"
}
```

**Approval:** all_of_n (doctor + pharmacist + CMO)
**First change triggers scope creep detection.**

## Billing

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/billing` | List billing records |
| POST | `/api/billing` | Create billing (triggers approval if >= $500) |
| POST | `/api/billing/{id}/appeal` | File insurance appeal |
| GET | `/api/billing/stats` | Billing statistics |

### POST /api/billing
```json
{
  "patient_id": "uuid",
  "description": "Coronary Artery Bypass Surgery",
  "procedure_code": "33533",
  "amount": 35000,
  "insurance_covered": 28000
}
```

**Step-up escalation:**
- < $500: auto-approve
- $500+: finance manager (specific)
- $10,000+: finance + director (step-up → all_of_n)
- $25,000+: finance + director + CMO (all_of_n, priority 10)

## HIPAA / Referrals

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/referrals` | List referrals (query: `referral_type`) |
| POST | `/api/referrals/external` | External clinic referral |
| POST | `/api/referrals/insurance-request` | Insurance data request |
| POST | `/api/referrals/research-export` | Research data export |

### POST /api/referrals/insurance-request
```json
{
  "patient_id": "uuid",
  "insurance_provider_id": "uuid",
  "requested_data_scope": "full",
  "reason": "Coverage review"
}
```

**Approval:** all_of_n with partial_approval (scope can be narrowed)

### POST /api/referrals/research-export
```json
{
  "referring_doctor_id": "uuid",
  "research_entity_name": "Stanford Research Lab",
  "research_entity_email": "research@stanford.edu",
  "reason": "Cardiovascular study",
  "patient_count": 150,
  "data_scope": "anonymized"
}
```

**Approval:** sequential (ethics board → CMO → hospital director)
**100+ patients triggers amount anomaly flag.**

## Emergency

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/emergency/events` | List all emergency events |
| GET | `/api/emergency/active` | Active emergencies only |
| POST | `/api/emergency/data-access` | Emergency data access (2-min timeout) |
| POST | `/api/emergency/security-breach` | Report security breach |
| POST | `/api/emergency/{id}/resolve` | Resolve emergency |

### POST /api/emergency/data-access
```json
{
  "patient_id": "uuid",
  "triggered_by": "paramedic@ambulance.com",
  "reason": "Need allergy info — patient in ambulance"
}
```

**Approval:** any_one, 120s timeout, no blackout, escalate on timeout

### POST /api/emergency/security-breach
```json
{
  "patient_id": "uuid",
  "triggered_by": "security.system@hospital.com",
  "reason": "Unauthorized access from IP 203.0.113.42",
  "severity": "critical"
}
```

**Immediate actions:** account freeze, Slack #security alert
**Approval:** all_of_n (security officer + CMO)

## Staff

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/staff/doctors` | List doctors |
| GET | `/api/staff/members` | List staff |
| POST | `/api/staff/access-request` | Request access change |
| POST | `/api/staff/doctors/{id}/delegate` | Set vacation delegation |
| DELETE | `/api/staff/doctors/{id}/delegate` | Clear delegation |
| GET | `/api/staff/shifts` | List shifts |

## Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/stats` | Aggregate statistics |
| GET | `/api/dashboard/activity` | Activity feed (query: `category`, `limit`) |
| GET | `/api/dashboard/activity/stream` | SSE real-time stream |
| GET | `/api/dashboard/approval-status` | Pending approvals |

## Scenarios

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scenarios` | List all 14 scenarios |
| GET | `/api/scenarios/{id}` | Scenario details |
| POST | `/api/scenarios/{id}/run` | Execute scenario (background) |

## System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/api/health` | Health check |
| POST | `/api/seed` | Seed database with demo data |
| GET | `/.well-known/agent.json` | A2A agent card |
| POST | `/a2a` | A2A JSON-RPC endpoint |
