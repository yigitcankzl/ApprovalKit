# ApprovalKit Demo Agents - Implementation Plan

> 36 industry-specific AI agents, each with chat-like interface,
> real-time approval flows via ApprovalKit, and interactive demo pages.

---

## Architecture Overview

### How Each Agent Works
1. User opens `/demos/[agentId]` - sees a chat-like interface
2. Predefined scenario buttons ("Quick Actions") let user trigger workflows
3. User can also type commands in the chat input
4. Agent processes the request, calling ApprovalKit-decorated functions
5. When approval is needed, chat shows "Waiting for approval..." with approve/reject buttons
6. On approval, the action executes via Token Vault and result shows in chat
7. Full audit trail visible in `/audit`

### Tech Stack Per Agent
- **Frontend**: `/demos/[agentId]/page.tsx` - Chat UI with scenario buttons
- **Backend**: `POST /api/v1/demo/agents/{agentId}/run` - Executes scenarios
- **Python Script**: `demos/{agent-name}/agent.py` - ApprovalKit SDK integration
- **Seed Data**: Connections + Approvers + Rules in `demo.py`

### Shared Components
- `AgentChat` - Reusable chat UI (messages, input, quick actions)
- `ApprovalBubble` - Inline approve/reject within chat
- `StepIndicator` - Shows multi-step progress (Step 1/5, Step 2/5...)
- Dynamic route `/demos/[agentId]/page.tsx` - Renders any agent

---

## Category 1: Ticaret & Finans (Commerce & Finance)

### 1. Invoice Agent - Otomatik Fatura ve Tahsilat

**Connections:** stripe-prod, gmail-prod, salesforce-prod
**Approvers:** CFO, Legal
**Chat Scenarios:**
- "Send invoice to client@example.com for $500" -> Auto (under $1000)
- "Send invoice for $2500 consulting fee" -> CFO approval
- "Send overdue payment reminder" -> Auto
- "Initiate legal collection for INV-2024-089" -> CFO + Legal step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| amount < $1000 | auto | - |
| amount $1000-$5000 | any_one | CFO |
| amount > $5000 | all_of_n | CFO + Legal |
| type = "legal_collection" | all_of_n | CFO + Legal |
| type = "overdue_reminder" | auto | - |

**Flow:**
```
User: "Send invoice $800 to client@acme.com"
Agent: Generating invoice INV-2026-0142...
Agent: Amount: $800 | Client: client@acme.com
Agent: [ApprovalKit] Under $1000 threshold - auto-approved
Agent: [Stripe] Payment link created: pay.stripe.com/inv_xxx
Agent: [Gmail] Invoice sent to client@acme.com
Agent: Done! Invoice INV-2026-0142 sent successfully.
```

### 2. Expense Approval Agent - Calisma Harcama Talepleri

**Connections:** stripe-prod, slack-prod, gmail-prod
**Approvers:** Manager, CFO
**Chat Scenarios:**
- "Request $45 for office supplies" -> Auto
- "Request $2500 for new laptop" -> Manager approval
- "Request $8000 for team offsite" -> CFO step-up
- "Partial approve: reduce from $3000 to $2000" -> Manager with param edit

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| category = "office_supplies" | auto | - |
| amount < $500 | auto | - |
| amount $500-$5000 | any_one | Manager |
| amount > $5000 | all_of_n | Manager + CFO |
| category = "equipment" | any_one | Manager |

### 3. Subscription Manager - Abonelik Yasam Dongusu

**Connections:** stripe-prod, slack-prod, gmail-prod
**Approvers:** Manager, CEO, CFO
**Chat Scenarios:**
- "Upgrade user@example.com from free to pro" -> Auto
- "Create enterprise plan for BigCorp" -> CEO approval
- "Process bulk cancellation (50 accounts)" -> CFO step-up
- "Apply 20% discount for annual commitment" -> Manager

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "free_to_paid" | auto | - |
| type = "enterprise_pricing" | specific | CEO |
| type = "bulk_cancel" & count > 10 | all_of_n | CFO + Manager |
| discount_pct > 30 | specific | CEO |

### 4. Vendor Payment Agent - Tedarikci Odeme Otomasyonu

**Connections:** stripe-prod, slack-prod, gmail-prod
**Approvers:** Finance, CFO, CEO, Procurement
**Chat Scenarios:**
- "Pay vendor CloudHost $800 for hosting" -> Auto (under $1000)
- "Pay vendor DataCorp $5000 for licenses" -> Finance approval
- "Pay new vendor NewTech $15000" -> CFO + CEO all_of_n
- "First payment to unverified vendor" -> Extra Procurement approval

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| amount < $1000 | auto | - |
| amount $1000-$10000 | any_one | Finance |
| amount > $10000 | all_of_n | CFO + CEO |
| is_new_vendor = true | all_of_n | Procurement + Finance |

### 5. Churn Prevention Agent - Musteri Kaybi Onleme

**Connections:** stripe-prod, salesforce-prod, gmail-prod
**Approvers:** Manager, CEO, CFO
**Chat Scenarios:**
- "Offer 10% retention discount to user@example.com" -> Auto
- "Offer 30% discount to enterprise leaving" -> Manager
- "Create custom package for VIP client" -> CEO
- "Enterprise custom pricing: $X/year" -> CEO + CFO sequential

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| discount_pct <= 10 | auto | - |
| discount_pct 11-30 | any_one | Manager |
| type = "custom_package" | specific | CEO |
| type = "enterprise_custom" | sequential | CEO -> CFO |

### 6. Carbon Credit Agent - Karbon Kredisi Alim Satim

**Connections:** stripe-prod, slack-prod, gmail-prod
**Approvers:** Sustainability Officer, CFO
**Chat Scenarios:**
- "Purchase 100 credits at $50/ton ($5000)" -> Auto (under $10000)
- "Purchase 500 credits at $45/ton ($22500)" -> Sustainability Officer
- "Sign 3-year forward contract for credits" -> CFO + Sustainability step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| total < $10000 | auto | - |
| total $10000-$50000 | any_one | Sustainability Officer |
| type = "forward_contract" | all_of_n | CFO + Sustainability Officer |
| total > $50000 | all_of_n | CFO + Sustainability Officer |

---

## Category 2: DevOps & Yazilim (DevOps & Software)

### 7. Release Manager Agent - Kod Deployment Yonetimi

**Connections:** github-main, slack-prod, pagerduty-prod
**Approvers:** Maintainer, On-Call Engineer, CTO
**Chat Scenarios:**
- "Deploy v2.5.0 to staging" -> Auto
- "Deploy v2.5.0 to production" -> Maintainer approval
- "Hotfix deploy at 3am" -> On-Call approval (blackout override)
- "Rollback production to v2.4.8" -> 2-minute timeout auto-rollback

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| env = "staging" | auto | - |
| env = "production" | any_one | Maintainer |
| type = "hotfix" & time in blackout | specific | On-Call Engineer |
| type = "rollback" | any_one | Maintainer (timeout: 120s, on_timeout: auto_approve) |

### 8. Security Incident Agent - Guvenlik Ihlali Mudahale

**Connections:** github-prod, slack-prod, pagerduty-prod
**Approvers:** Security Lead, CTO
**Chat Scenarios:**
- "Log security alert: suspicious login from IP 1.2.3.4" -> Auto
- "Lock repository acme/api for investigation" -> Security Lead
- "Revoke all production access tokens" -> CTO + Security Lead all_of_n
- "Kill compromised service instance" -> Security Lead (urgent)

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "alert_log" | auto | - |
| type = "repo_lock" | specific | Security Lead |
| type = "revoke_access" | all_of_n | CTO + Security Lead |
| type = "kill_service" | specific | Security Lead (urgent channel) |

### 9. Dependency Update Agent - Paket Guncelleme Yonetimi

**Connections:** github-prod, slack-prod
**Approvers:** Lead Engineer, Team (all)
**Chat Scenarios:**
- "Update lodash 4.17.20 -> 4.17.21 (patch)" -> Auto
- "Update react 18.2 -> 18.3 (minor)" -> Lead Engineer
- "Update webpack 5.x -> 6.0 (major breaking)" -> All team approval

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| update_type = "patch" | auto | - |
| update_type = "minor" | any_one | Lead Engineer |
| update_type = "major" | all_of_n | Lead Engineer + Maintainer + CTO |

### 10. Database Migration Agent - Schema Degisiklik Yonetimi

**Connections:** github-prod, slack-prod
**Approvers:** DBA, CTO
**Chat Scenarios:**
- "Run migration on dev: add index on users.email" -> Auto
- "Run migration on staging: alter table orders" -> DBA approval
- "Run migration on production: drop column" -> DBA + CTO step-up
- "Migration during blackout window (2am-5am)" -> Blocked

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| env = "dev" | auto | - |
| env = "staging" | any_one | DBA |
| env = "production" | all_of_n | DBA + CTO |
| blackout 02:00-05:00 | blocked | - |

### 11. API Key Rotation Agent - Credential Dondurme

**Connections:** github-prod, slack-prod, gmail-prod
**Approvers:** Security Lead, CTO
**Chat Scenarios:**
- "Rotate scheduled Stripe API key" -> Auto
- "Emergency rotate compromised AWS key" -> Security Lead
- "Rotate third-party partner API key" -> CTO step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "scheduled" | auto | - |
| type = "emergency" | specific | Security Lead |
| type = "third_party" | all_of_n | Security Lead + CTO |

### 12. Compliance Audit Agent - Duzenleyici Uyum

**Connections:** gmail-prod, slack-prod, salesforce-prod
**Approvers:** Compliance Officer, Legal, CEO
**Chat Scenarios:**
- "Run routine SOC2 compliance check" -> Auto
- "Report: GDPR violation detected in user data" -> Compliance Officer
- "File official report to regulatory body" -> Legal + CEO step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "routine_check" | auto | - |
| type = "violation_report" | specific | Compliance Officer |
| type = "regulatory_filing" | all_of_n | Legal + CEO |

---

## Category 3: Insan Kaynaklari (Human Resources)

### 13. Recruitment Agent - Tam Ise Alim Sureci

**Connections:** gmail-prod, slack-prod, github-prod, calendar-prod
**Approvers:** HR Manager, CFO, CEO
**Chat Scenarios:**
- "Send interview invite to candidate@example.com" -> Auto
- "Send offer letter: $180k Senior Engineer" -> HR Manager
- "Salary package with equity: $220k + 0.5%" -> HR + CFO sequential
- "Terminate employee: performance review" -> HR + CEO all_of_n

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "interview_invite" | auto | - |
| type = "offer_letter" | specific | HR Manager |
| type = "salary_package" | sequential | HR Manager -> CFO |
| type = "termination" | all_of_n | HR Manager + CEO |

### 14. Access Provisioning Agent - Sistem Erisim Yonetimi

**Connections:** github-prod, slack-prod, gmail-prod
**Approvers:** IT Manager, CTO, CFO
**Chat Scenarios:**
- "Grant standard repo access to new hire" -> IT Manager
- "Grant admin access to platform" -> CTO approval
- "Grant financial system access" -> CFO + CTO step-up
- "Revoke all access for departing employee" -> Auto (immediate)

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "standard_access" | any_one | IT Manager |
| type = "admin_access" | specific | CTO |
| type = "financial_access" | all_of_n | CFO + CTO |
| type = "revoke_departed" | auto | - |

### 15. Leave Management Agent - Izin Yonetimi

**Connections:** slack-prod, calendar-prod, gmail-prod
**Approvers:** Manager, HR Manager, CEO
**Chat Scenarios:**
- "Request 1 day off next Friday" -> Auto (1-2 days)
- "Request 1 week vacation March 15-22" -> Manager
- "Request 3 month sabbatical" -> HR Manager
- "Request leave during product launch week" -> CEO step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| days <= 2 | auto | - |
| days 3-5 | any_one | Manager |
| days > 20 | specific | HR Manager |
| is_critical_period = true | all_of_n | Manager + CEO |

### 16. Contractor Onboarding Agent - Freelancer Ise Alim

**Connections:** gmail-prod, stripe-prod, github-prod
**Approvers:** Legal, CEO, Manager
**Chat Scenarios:**
- "Send NDA to contractor@example.com" -> Auto
- "Set up payment agreement: $5000/month" -> Legal
- "Sign $15000+ contract with external firm" -> CEO step-up
- "Grant repo access to contractor" -> Manager

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "nda" | auto | - |
| type = "payment_agreement" | specific | Legal |
| contract_value > $10000 | all_of_n | Legal + CEO |
| type = "repo_access" | any_one | Manager |

### 17. Performance Review Agent - Performans ve Terfi

**Connections:** gmail-prod, slack-prod
**Approvers:** HR Manager, Manager, CFO
**Chat Scenarios:**
- "Send quarterly review form to team" -> Auto
- "Submit promotion recommendation for Alice" -> HR + Manager
- "Process salary increase: $150k -> $175k" -> HR + CFO sequential

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "review_form" | auto | - |
| type = "promotion" | all_of_n | HR Manager + Manager |
| type = "salary_increase" | sequential | HR Manager -> CFO |

---

## Category 4: Musteri Hizmetleri (Customer Service)

### 18. Support Escalation Agent - Musteri Sikayet Yonetimi

**Connections:** salesforce-prod, slack-prod, gmail-prod, stripe-prod
**Approvers:** CS Manager, CFO, Legal
**Chat Scenarios:**
- "Handle standard complaint: shipping delay" -> Auto response
- "VIP customer complaint: service outage" -> CS Manager
- "Process $5000 compensation claim" -> CFO + Legal step-up
- "Issue $50 goodwill credit" -> Auto

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "standard" | auto | - |
| customer_tier = "vip" | specific | CS Manager |
| compensation > $1000 | all_of_n | CFO + Legal |
| type = "goodwill_credit" & amount < $100 | auto | - |

### 19. Account Takeover Response Agent - Hesap Guvenlik Ihlali

**Connections:** salesforce-prod, slack-prod, gmail-prod
**Approvers:** Security Lead, Legal
**Chat Scenarios:**
- "Alert: suspicious activity on account user@example.com" -> Auto notify
- "Freeze account pending investigation" -> Security Lead
- "Permanently ban account for fraud" -> Security + Legal all_of_n

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "alert" | auto | - |
| type = "freeze" | specific | Security Lead |
| type = "permanent_ban" | all_of_n | Security Lead + Legal |

### 20. SLA Breach Agent - Hizmet Seviyesi Ihlal

**Connections:** stripe-prod, slack-prod, gmail-prod
**Approvers:** CS Manager, CFO, Legal
**Chat Scenarios:**
- "SLA breach notification: 99.5% -> 98.2% uptime" -> Auto notify
- "Process SLA credit: $2000 service credit" -> CS Manager
- "Major SLA breach compensation: $50000" -> CFO + Legal step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "notification" | auto | - |
| type = "credit" & amount < $5000 | any_one | CS Manager |
| type = "compensation" & amount >= $5000 | all_of_n | CFO + Legal |

---

## Category 5: Saglik & Klinik (Health & Clinical)

### 21. Patient Data Sharing Agent - Hasta Dosyasi Paylasimi

**Connections:** gdrive-prod, gmail-prod, slack-prod
**Approvers:** Doctor, Patient Representative
**Chat Scenarios:**
- "Share records with patient's primary doctor" -> Auto
- "Share records with external clinic" -> Doctor approval
- "Share records with insurance company" -> Patient + Doctor step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| recipient = "own_doctor" | auto | - |
| recipient = "external_clinic" | specific | Doctor |
| recipient = "insurance" | all_of_n | Patient Rep + Doctor |

### 22. Medical Supply Agent - Klinik Malzeme Siparisi

**Connections:** stripe-prod, slack-prod, gmail-prod
**Approvers:** Chief Doctor, CFO
**Chat Scenarios:**
- "Order standard supplies: gloves, masks ($200)" -> Auto
- "Order expensive equipment: MRI contrast ($5000)" -> Chief Doctor
- "Purchase new diagnostic device ($50000)" -> Chief Doctor + CFO all_of_n

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| category = "consumable" & amount < $1000 | auto | - |
| amount $1000-$20000 | specific | Chief Doctor |
| amount > $20000 | all_of_n | Chief Doctor + CFO |

### 23. Prescription Refill Agent - Ilac Yenileme

**Connections:** gmail-prod, slack-prod
**Approvers:** Doctor, Pharmacist
**Chat Scenarios:**
- "Refill routine medication: Metformin 500mg" -> Auto
- "Refill controlled substance: Adderall 20mg" -> Doctor approval
- "Change dosage: Lisinopril 10mg -> 20mg" -> Doctor + Pharmacist sequential

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "routine" | auto | - |
| type = "controlled" | specific | Doctor |
| type = "dosage_change" | sequential | Doctor -> Pharmacist |

### 24. Research Data Agent - Klinik Arastirma Veri Erisimi

**Connections:** gdrive-prod, gmail-prod, slack-prod
**Approvers:** Ethics Board, Chief Doctor
**Chat Scenarios:**
- "Access anonymized dataset for study XYZ" -> Auto
- "Access patient-level data for clinical trial" -> Ethics Board
- "Share data with external research institution" -> Ethics Board + Chief Doctor all_of_n

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "anonymized" | auto | - |
| type = "patient_level" | specific | Ethics Board |
| type = "external_share" | all_of_n | Ethics Board + Chief Doctor |

---

## Category 6: Egitim (Education)

### 25. Grade Override Agent - Not Duzeltme Yonetimi

**Connections:** gmail-prod, slack-prod, gsheets-prod
**Approvers:** Teacher, Department Head
**Chat Scenarios:**
- "Fix administrative error: Student #1234 midterm 72 -> 78" -> Auto
- "Grade appeal: raise final grade B -> B+" -> Teacher approval
- "Override final course grade" -> Department Head step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "admin_error" | auto | - |
| type = "grade_appeal" | specific | Teacher |
| type = "final_override" | all_of_n | Teacher + Department Head |

### 26. Scholarship Agent - Burs Yonetimi

**Connections:** gmail-prod, stripe-prod, slack-prod
**Approvers:** Committee, Rector
**Chat Scenarios:**
- "Accept scholarship application from student" -> Auto (record)
- "Award $5000 merit scholarship" -> Committee
- "Award full scholarship ($40000/year)" -> Rector + Committee all_of_n

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "application" | auto | - |
| type = "award" & amount < $10000 | any_one | Committee |
| type = "full_scholarship" | all_of_n | Rector + Committee |

### 27. Research Grant Agent - Arastirma Fonu Yonetimi

**Connections:** stripe-prod, gmail-prod, slack-prod
**Approvers:** Department Head, Rector
**Chat Scenarios:**
- "Approve $3000 lab equipment purchase from grant" -> Department Head
- "Approve $25000 conference sponsorship" -> Rector
- "Approve $75000 external collaboration" -> Rector + External Board sequential

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| amount < $5000 | any_one | Department Head |
| amount $5000-$50000 | specific | Rector |
| amount > $50000 | sequential | Rector -> External Board |

---

## Category 7: Hukuk & Uyum (Legal & Compliance)

### 28. Contract Signing Agent - Sozlesme Imzalama

**Connections:** gmail-prod, slack-prod, dropbox-prod
**Approvers:** Legal, CEO
**Chat Scenarios:**
- "Send standard NDA to partner@example.com" -> Auto
- "Send service agreement for review" -> Legal
- "Sign partnership agreement" -> CEO + Legal all_of_n

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "nda" | auto | - |
| type = "service_agreement" | specific | Legal |
| type = "partnership" | all_of_n | CEO + Legal |

### 29. GDPR Request Agent - Veri Silme Talep Yonetimi

**Connections:** gmail-prod, slack-prod, github-prod
**Approvers:** Privacy Officer, CTO
**Chat Scenarios:**
- "Log GDPR data request from user@example.com" -> Auto
- "Execute data deletion for user account" -> Privacy Officer
- "Bulk data deletion (500+ records)" -> CTO + Privacy Officer step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "request_log" | auto | - |
| type = "single_delete" | specific | Privacy Officer |
| type = "bulk_delete" | all_of_n | CTO + Privacy Officer |

### 30. IP Filing Agent - Fikri Mulkiyet Basvurusu

**Connections:** gmail-prod, dropbox-prod, slack-prod
**Approvers:** Legal, CEO
**Chat Scenarios:**
- "Prepare patent draft for new algorithm" -> Auto (draft only)
- "File domestic patent application" -> Legal
- "File international patent (PCT)" -> CEO + Legal all_of_n

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "draft" | auto | - |
| type = "domestic_filing" | specific | Legal |
| type = "international_filing" | all_of_n | CEO + Legal |

---

## Category 8: Gayrimenkul (Real Estate)

### 31. Maintenance Request Agent - Bina Bakim Talepleri

**Connections:** stripe-prod, slack-prod, gmail-prod
**Approvers:** Building Manager, Property Owner
**Chat Scenarios:**
- "Fix leaky faucet in Unit 4B ($200)" -> Auto (under $500)
- "Replace HVAC unit ($3000)" -> Building Manager
- "Major roof repair ($15000)" -> Property Owner step-up
- "Emergency: burst pipe (no blackout)" -> Auto immediate

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| amount < $500 | auto | - |
| amount $500-$5000 | any_one | Building Manager |
| amount > $5000 | all_of_n | Building Manager + Property Owner |
| type = "emergency" | auto (no blackout) | - |

### 32. Tenant Screening Agent - Kiraci Basvuru Yonetimi

**Connections:** gmail-prod, slack-prod, stripe-prod
**Approvers:** Property Manager, Legal
**Chat Scenarios:**
- "Run credit check on applicant" -> Auto
- "Review application with past eviction" -> Property Manager
- "Applicant with criminal record" -> Legal step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "credit_check" | auto | - |
| type = "eviction_history" | specific | Property Manager |
| type = "criminal_check" | all_of_n | Property Manager + Legal |

---

## Category 9: Medya & Icerik (Media & Content)

### 33. Content Moderation Agent - Platform Icerik Moderasyonu

**Connections:** slack-prod, gmail-prod
**Approvers:** Moderator, Senior Moderator, Legal
**Chat Scenarios:**
- "Auto-remove detected spam content" -> Auto
- "Flag suspicious content for review" -> Moderator
- "Ban user account permanently" -> Senior Moderator + Legal step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "spam" | auto | - |
| type = "suspicious" | any_one | Moderator |
| type = "account_ban" | all_of_n | Senior Moderator + Legal |

### 34. Licensing Agent - Icerik Lisanslama Yonetimi

**Connections:** stripe-prod, gmail-prod, slack-prod
**Approvers:** Legal, CEO
**Chat Scenarios:**
- "Issue standard personal license" -> Auto
- "Issue commercial license for media company" -> Legal
- "Sign major media deal ($100k+)" -> CEO + Legal all_of_n

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "personal" | auto | - |
| type = "commercial" | specific | Legal |
| type = "major_deal" & amount > $100000 | all_of_n | CEO + Legal |

---

## Category 10: Enerji & Cevre (Energy & Environment)

### 35. Environmental Incident Agent - Cevre Ihlali Yonetimi

**Connections:** gmail-prod, slack-prod
**Approvers:** Environmental Officer, CEO, Regulator Contact
**Chat Scenarios:**
- "Log routine environmental monitoring data" -> Auto
- "Report minor chemical spill in lab" -> Auto notify
- "Major environmental incident: containment breach" -> CEO + Environmental Officer + Regulator all_of_n

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| type = "monitoring" | auto | - |
| type = "minor_spill" | auto (notify) | - |
| type = "major_incident" | all_of_n | CEO + Environmental Officer |

### 36. Renewable Energy Purchase Agent - Yenilenebilir Enerji

**Connections:** stripe-prod, gmail-prod, slack-prod
**Approvers:** CFO, CEO, Board
**Chat Scenarios:**
- "Purchase 100 MWh solar credits ($8000)" -> Auto (small lot)
- "Purchase 1000 MWh wind credits ($75000)" -> CFO
- "Sign 5-year PPA agreement ($500k)" -> CEO + CFO + Board step-up

**Rules:**
| Condition | Model | Approvers |
|-----------|-------|-----------|
| total < $10000 | auto | - |
| total $10000-$100000 | any_one | CFO |
| type = "long_term_agreement" | all_of_n | CEO + CFO |
| total > $100000 | all_of_n | CEO + CFO |

---

## New Connections Required

| Slug | Service | Actions |
|------|---------|---------|
| stripe-prod | stripe | charge, refund, payout, wire_transfer, vendor_payment, subscription, credit |
| gmail-prod | gmail | send_email, press_release |
| slack-prod | slack | send_message |
| github-prod | github | add_member, remove_member, deploy, rollback, merge_pr, lock_repo, revoke_tokens |
| github-main | github | deploy, rollback, merge_pr |
| salesforce-prod | salesforce | update_case, create_ticket, log_complaint |
| pagerduty-prod | pagerduty | create_incident, notify_oncall |
| calendar-prod | google_calendar | create_event, block_time |
| gdrive-prod | google_drive | share_file, create_folder |
| gsheets-prod | google_sheets | update_sheet, create_sheet |
| dropbox-prod | dropbox | upload_file, share_folder |

## New Approver Roles Required

| Role | Name | Used By Agents |
|------|------|----------------|
| security_lead | Security Lead | 8, 11, 19 |
| compliance_officer | Compliance Officer | 12 |
| dba | Database Admin | 10 |
| sustainability_officer | Sustainability Officer | 6 |
| oncall_engineer | On-Call Engineer | 7 |
| doctor | Doctor | 21, 23 |
| patient_rep | Patient Representative | 21 |
| chief_doctor | Chief Doctor | 22, 24 |
| pharmacist | Pharmacist | 23 |
| ethics_board | Ethics Board | 24 |
| teacher | Teacher | 25 |
| department_head | Department Head | 25, 27 |
| scholarship_committee | Scholarship Committee | 26 |
| rector | Rector | 26, 27 |
| privacy_officer | Privacy Officer | 29 |
| building_manager | Building Manager | 31 |
| property_owner | Property Owner | 31 |
| property_manager | Property Manager | 32 |
| moderator | Moderator | 33 |
| senior_moderator | Senior Moderator | 33 |
| environmental_officer | Environmental Officer | 35 |
| board | Board Member | 36 |
| external_board | External Board | 27 |

---

## Implementation Order

### Phase 1: Infrastructure
1. Shared `AgentChat` component
2. Dynamic route `/demos/[agentId]/page.tsx`
3. Backend chat endpoint `POST /api/v1/demo/agents/{id}/run`
4. Extend seed data (connections, approvers)

### Phase 2: Finance Agents (1-6)
### Phase 3: DevOps Agents (7-12)
### Phase 4: HR Agents (13-17)
### Phase 5: Customer Service (18-20)
### Phase 6: Healthcare (21-24)
### Phase 7: Education (25-27)
### Phase 8: Legal (28-30)
### Phase 9: Real Estate + Media + Energy (31-36)

Each phase: Create agent folders, Python scripts, add to demo catalog, commit.
