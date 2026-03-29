# Healthcare AI Agent — Approval Flows

## Complete Approval Matrix

| # | Scenario | Connection | Action | Model | Approvers | Special Features |
|---|----------|------------|--------|-------|-----------|-----------------|
| 1 | Patient Onboarding | gmail, slack, gcal | send_email, send_message, create_event | auto | — | Token Vault notifications |
| 2 | Routine Prescription | healthcare-rx | prescribe | specific | Doctor | — |
| 3 | Controlled Substance | healthcare-rx | prescribe_controlled | sequential | Doctor → Pharmacist | Order matters |
| 4 | Dose Change | healthcare-rx | dose_change | all_of_n | Doctor + Pharmacist + CMO | Scope creep on first change |
| 5 | External Referral | healthcare-hipaa | external_referral | specific | Doctor | Drive share + Gmail notify |
| 6 | Insurance Data | healthcare-hipaa | insurance_data | all_of_n | Patient Rep + Doctor | partial_approval (scope narrowing) |
| 7 | Research Export | healthcare-hipaa | research_export | sequential | Ethics → CMO → Director | Amount anomaly (100+ patients) |
| 8 | Small Billing (<$500) | healthcare-billing | charge | auto | — | No rule match = auto-approve |
| 9 | Standard Billing ($500+) | healthcare-billing | charge | specific | Finance Manager | Blackout 22:00-06:00 |
| 10 | Large Billing ($10k+) | healthcare-billing | charge | step-up → all_of_n | Finance + Director | Step-up from specific |
| 11 | Major Billing ($25k+) | healthcare-billing | charge | all_of_n | Finance + Director + CMO | Highest priority rule |
| 12 | Insurance Appeal | healthcare-billing | appeal | all_of_n | Doctor + Finance | — |
| 13 | Emergency Data Access | healthcare-emergency | emergency_access | any_one | Any doctor / CMO | 2-min timeout, no blackout |
| 14 | Security Breach | healthcare-emergency | security_freeze | all_of_n | Security + CMO | Auto-freeze first |
| 15 | Basic Staff Access | healthcare-hr | access_change | specific | IT Admin | — |
| 16 | Patient Records Access | healthcare-hr | access_change | step-up → all_of_n | IT + CMO | Step-up from specific |
| 17 | Medication System Access | healthcare-hr | access_change | all_of_n | IT + Pharmacy Lead + CMO | Priority 10 |

## Detailed Flow Descriptions

### Flow 3: Controlled Substance (Sequential)

```
Agent creates prescription (is_controlled=true, schedule_class="II")
  │
  ▼
ApprovalKit: healthcare-rx / prescribe_controlled
  │
  ▼
Rule Engine: matches "Controlled Substance Prescription" rule
  │ Model: sequential
  │ Approvers: [Doctor (order=0), Pharmacist (order=1)]
  │
  ▼
Celery Worker:
  1. CIBA push → Doctor's Guardian app
     "CONTROLLED Rx Adderall (II) for MRN-00001"
     Doctor taps APPROVE ✓
  │
  2. CIBA push → Pharmacist's Guardian app
     "CONTROLLED Rx Adderall (II) for MRN-00001"
     Pharmacist taps APPROVE ✓
  │
  ▼
Token Vault executes
  │
  ▼
Agent receives: {"status": "approved", "final_params": {...}}
  │
  ▼
Notification Service:
  → Gmail to pharmacy (Token Vault)
  → Activity log entry
```

### Flow 6: Insurance Data with Partial Approval

```
Insurance requests patient data (data_scope="full")
  │
  ▼
ApprovalKit: healthcare-hipaa / insurance_data
  │ Rule: all_of_n + partial_approval=true
  │ Approvers: [Patient Representative, Doctor]
  │
  ▼
Patient Rep approves ✓
Doctor reviews and MODIFIES params:
  requested_data_scope: "full" → "summary"
Doctor approves with modified params ✓
  │
  ▼
Agent receives:
  {"status": "approved", "final_params": {"requested_data_scope": "summary"}}
  │
  ▼
Agent checks final_params.requested_data_scope:
  Original: "full" → Final: "summary"
  → Scope was narrowed by approver
  │
  ▼
Share SUMMARY records only (not full) via Google Drive
```

### Flow 9-11: Billing Step-Up Escalation

```
$200 invoice → No rule matches → Auto-approve ✓
  │
$800 invoice → "Standard Billing ($500+)" rule matches
  │ Model: specific (Finance Manager only)
  │ → Finance Manager approves ✓
  │
$15,000 invoice → Same rule matches, BUT step_up_conditions trigger:
  │ amount >= 10000 → ESCALATE
  │ Step-up model: all_of_n
  │ Step-up approvers: [Finance Manager, Hospital Director]
  │ → Both must approve ✓
  │
$35,000 invoice → "Major Billing ($25k+)" rule matches (priority=10, higher than standard)
  │ Model: all_of_n
  │ Approvers: [Finance Manager, Hospital Director, CMO]
  │ → All three must approve ✓
  │
After approval:
  → Slack #billing alert
  → Gmail insurance claim
```

### Flow 13: Emergency Access (2-Minute Timeout)

```
Paramedic needs allergy info — patient in ambulance
  │
  ▼
EmergencyService:
  1. Create EmergencyEvent (status=active)
  2. Slack #emergency alert (IMMEDIATE, before approval)
  │
  ▼
ApprovalKit: healthcare-emergency / emergency_access
  │ Model: any_one
  │ Approvers: [Any doctor, CMO]
  │ Timeout: 120 seconds
  │ Blackout: NONE (emergency override)
  │ On timeout: ESCALATE to CMO
  │
  ▼
SDK polls with poll_interval=2s, timeout=130s
  │
  ├─ Doctor approves within 2 min → Access granted ✓
  │  → Google Drive shares full records
  │  → Special audit: "emergency access" event type
  │
  └─ Timeout (no response) → ESCALATE to CMO
     → CMO gets Guardian push
     → If CMO also times out → Blocked (logged)
```

## ApprovalKit Feature Map

| Feature | Where Used | How |
|---------|-----------|-----|
| **Token Vault** | All notifications | Gmail, Slack, Calendar, Drive via Auth0 Token Exchange |
| **CIBA Guardian** | All approval-required actions | Push notification to approver's phone |
| **any_one** | Emergency access | First available doctor approves |
| **specific** | Routine Rx, external referral | Designated doctor approves |
| **all_of_n** | Dose change, insurance data, security breach | Every listed approver must approve |
| **sequential** | Controlled substance, research export | Approvers in specific order |
| **k_of_n** | Available (ethics board 3/5) | k out of n approvals |
| **step-up** | Billing ($500→$10k), staff access | Escalate approval model on conditions |
| **partial_approval** | Insurance data request | Approver can narrow data scope |
| **delegation** | Doctor vacation | Approval authority transfers to delegate |
| **blackout_window** | Standard billing | No billing operations 22:00-06:00 |
| **cooldown** | Available per rule | Rate-limit requests per hour |
| **scope_creep** | Dose change (first time) | Auto-detected by ApprovalKit |
| **amount_anomaly** | Research export (100+ patients) | Auto-flagged when count > 3x avg |
| **audit_trail** | Everything | Immutable, PII-masked event log |
| **timeout_escalation** | Emergency access | On timeout → escalate to CMO |
