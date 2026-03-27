"""
Agent Chat Engine
=================
Intent-based conversational engine for demo agents.
Each agent defines intents (patterns + parameter extraction) that map
user messages to ApprovalKit actions.

Flow:
  1. User types message
  2. Engine matches intent via keyword/regex patterns
  3. Extracts parameters from the message
  4. Returns a structured response with action to execute
  5. Frontend sends the action to POST /api/v1/test-request
"""

import re
from typing import Any

# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_amount(text: str) -> float | None:
    """Extract dollar amount from text."""
    m = re.search(r'\$\s?([\d,]+(?:\.\d+)?)', text)
    if m:
        return float(m.group(1).replace(',', ''))
    m = re.search(r'(\d[\d,]*(?:\.\d+)?)\s*(?:dollar|usd|dolar)', text, re.I)
    if m:
        return float(m.group(1).replace(',', ''))
    return None


def _extract_email(text: str) -> str | None:
    m = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
    return m.group(0) if m else None


def _extract_number(text: str) -> int | None:
    m = re.search(r'\b(\d+)\b', text)
    return int(m.group(1)) if m else None


def _extract_percentage(text: str) -> int | None:
    m = re.search(r'(\d+)\s*%', text)
    return int(m.group(1)) if m else None


def _extract_name(text: str, after_keyword: str) -> str | None:
    """Extract a name/phrase after a keyword."""
    m = re.search(rf'{after_keyword}\s+(.+?)(?:\s+for|\s+to|\s+from|\s*$)', text, re.I)
    return m.group(1).strip() if m else None


def _kw_match(text: str, keywords: list[str]) -> bool:
    """Check if any keyword appears in text (case-insensitive)."""
    lower = text.lower()
    return any(k.lower() in lower for k in keywords)


# ── Intent Definition ──────────────────────────────────────────────────────────

class Intent:
    def __init__(self, name: str, keywords: list[str], connection: str, action: str,
                 param_builder, response_template: str, priority: int = 0):
        self.name = name
        self.keywords = keywords
        self.connection = connection
        self.action = action
        self.param_builder = param_builder  # fn(text) -> dict | None
        self.response_template = response_template
        self.priority = priority


# ── Agent Chat Definitions ─────────────────────────────────────────────────────

def _build_agent_intents() -> dict[str, list[Intent]]:
    """Build intent lists for all 36 agents."""
    agents: dict[str, list[Intent]] = {}

    # ── Invoice Agent ────────────────────────────────────────────────────
    agents["invoice"] = [
        Intent("legal_collection", ["legal", "collection", "hukuki", "dava", "sue"],
               "gmail-prod", "send_email",
               lambda t: {"type": "legal_collection", "customer": _extract_email(t) or "delinquent@example.com",
                          "amount_usd": _extract_amount(t) or 15000, "subject": "Final Notice"},
               "Initiating legal collection process for {customer}. Amount: ${amount_usd}. This requires CFO + Legal approval.", 10),
        Intent("send_invoice", ["invoice", "fatura", "bill", "send invoice", "create invoice"],
               "stripe-prod", "charge",
               lambda t: {"type": "invoice", "amount_usd": _extract_amount(t) or 500,
                          "customer": _extract_email(t) or "client@example.com",
                          "description": "Invoice " + (t[:50] if len(t) > 10 else "Services rendered")},
               "Creating invoice for {customer}. Amount: ${amount_usd}.", 0),
        Intent("overdue_reminder", ["overdue", "reminder", "hatirlatma", "gecikmi", "late payment"],
               "gmail-prod", "send_email",
               lambda t: {"type": "overdue_reminder", "recipient": _extract_email(t) or "debtor@example.com",
                          "subject": "Payment Overdue Reminder"},
               "Sending overdue payment reminder to {recipient}. This auto-processes.", 5),
    ]

    # ── Expense Agent ────────────────────────────────────────────────────
    agents["expense"] = [
        Intent("submit_expense", ["expense", "harcama", "reimburse", "buy", "purchase", "satin al"],
               "stripe-prod", "charge",
               lambda t: {
                   "type": "expense",
                   "amount_usd": _extract_amount(t) or 100,
                   "category": "equipment" if _kw_match(t, ["laptop", "computer", "ekipman", "equipment", "monitor"]) else
                              "team_event" if _kw_match(t, ["team", "offsite", "event", "dinner"]) else
                              "travel" if _kw_match(t, ["travel", "flight", "hotel", "seyahat"]) else "office_supplies",
                   "description": t[:80],
               },
               "Submitting expense request: {description}\nAmount: ${amount_usd} | Category: {category}", 0),
    ]

    # ── Subscription Manager ─────────────────────────────────────────────
    agents["subscription"] = [
        Intent("bulk_cancel", ["bulk cancel", "toplu iptal", "mass cancel", "cancel all"],
               "stripe-prod", "subscription",
               lambda t: {"type": "bulk_cancel", "count": _extract_number(t) or 50, "reason": "Product sunset"},
               "Processing bulk cancellation of {count} subscriptions. This requires CFO + Manager approval.", 10),
        Intent("enterprise", ["enterprise", "kurumsal", "custom plan", "ozel fiyat"],
               "stripe-prod", "subscription",
               lambda t: {"type": "enterprise_pricing", "customer": _extract_email(t) or "enterprise@bigcorp.com",
                          "amount_usd": _extract_amount(t) or 5000},
               "Creating enterprise pricing for {customer}: ${amount_usd}/mo. CEO approval required.", 5),
        Intent("upgrade", ["upgrade", "yukselt", "switch to", "change plan"],
               "stripe-prod", "subscription",
               lambda t: {"type": "upgrade", "customer": _extract_email(t) or "user@example.com",
                          "plan": "pro", "amount_usd": 29},
               "Upgrading {customer} to Pro plan (${amount_usd}/mo). Auto-approved.", 0),
    ]

    # ── Vendor Payment Agent ─────────────────────────────────────────────
    agents["vendor_payment"] = [
        Intent("pay_vendor", ["pay", "ode", "vendor", "tedarikci", "supplier"],
               "stripe-prod", "vendor_payment",
               lambda t: {
                   "amount_usd": _extract_amount(t) or 1000,
                   "vendor_name": _extract_name(t, "(?:pay|to)") or "Vendor Co",
                   "invoice_id": "INV-" + str(hash(t))[:6].upper(),
                   "is_new_vendor": _kw_match(t, ["new vendor", "yeni", "first time", "ilk"]),
               },
               "Processing payment of ${amount_usd} to {vendor_name}. Invoice: {invoice_id}", 0),
    ]

    # ── Churn Prevention Agent ───────────────────────────────────────────
    agents["churn_prevention"] = [
        Intent("enterprise_custom", ["enterprise custom", "kurumsal ozel", "custom pricing"],
               "stripe-prod", "credit",
               lambda t: {"type": "enterprise_custom", "customer": _extract_email(t) or "vip@enterprise.com",
                          "amount_usd": _extract_amount(t) or 50000},
               "Creating enterprise custom pricing for {customer}: ${amount_usd}/yr. CEO + CFO required.", 10),
        Intent("custom_package", ["custom package", "ozel paket", "bespoke", "special offer"],
               "stripe-prod", "credit",
               lambda t: {"type": "custom_package", "customer": _extract_email(t) or "vip@example.com",
                          "description": "Custom retention package"},
               "Creating custom retention package for {customer}. CEO approval required.", 5),
        Intent("offer_discount", ["discount", "indirim", "retention", "offer", "teklif"],
               "stripe-prod", "credit",
               lambda t: {"discount_pct": _extract_percentage(t) or 10,
                          "customer": _extract_email(t) or "leaving@example.com",
                          "reason": "Retention offer"},
               "Offering {discount_pct}% retention discount to {customer}.", 0),
    ]

    # ── Carbon Credit Agent ──────────────────────────────────────────────
    agents["carbon_credit"] = [
        Intent("forward_contract", ["forward", "contract", "sozlesme", "long-term", "anla"],
               "stripe-prod", "charge",
               lambda t: {"type": "carbon_forward", "amount_usd": _extract_amount(t) or 150000,
                          "years": _extract_number(t) or 3, "annual_tons": 1000},
               "Signing {years}-year forward contract for ${amount_usd}. CFO + Sustainability required.", 10),
        Intent("purchase_credits", ["carbon", "credit", "kredi", "offset", "purchase", "buy", "satin"],
               "stripe-prod", "charge",
               lambda t: {
                   "type": "carbon_credit",
                   "amount_usd": _extract_amount(t) or 5000,
                   "quantity": (_extract_amount(t) or 5000) // 50,
                   "price_per_ton": 50,
               },
               "Purchasing {quantity} carbon credits at $50/ton (${amount_usd} total).", 0),
    ]

    # ── Release Manager Agent ────────────────────────────────────────────
    agents["release_manager"] = [
        Intent("rollback", ["rollback", "geri al", "revert"],
               "github-main", "rollback",
               lambda t: {"env": "production", "version": "v2.4.8", "reason": t[:60]},
               "Rolling back production to {version}. Reason: {reason}. 2-min timeout.", 10),
        Intent("hotfix", ["hotfix", "acil", "emergency deploy", "urgent"],
               "github-main", "deploy",
               lambda t: {"type": "hotfix", "ref": "hotfix/urgent", "environment": "production", "service": "api"},
               "Deploying hotfix to production. On-call engineer approval needed.", 5),
        Intent("deploy", ["deploy", "release", "ship", "yayinla", "cikart"],
               "github-main", "deploy",
               lambda t: {
                   "ref": "v2.5.0",
                   "environment": "production" if _kw_match(t, ["prod", "production", "canli"]) else "staging",
                   "service": "api",
               },
               "Deploying {ref} to {environment}.", 0),
    ]

    # ── Security Incident Agent ──────────────────────────────────────────
    agents["security_incident"] = [
        Intent("revoke_tokens", ["revoke", "token", "iptal", "kill all"],
               "github-prod", "revoke_tokens",
               lambda t: {"scope": "production", "reason": t[:60]},
               "CRITICAL: Revoking all production access tokens. CTO + Security Lead required.", 10),
        Intent("lock_repo", ["lock", "kilitle", "freeze repo"],
               "github-prod", "lock_repo",
               lambda t: {"repo": "acme/api", "reason": t[:60]},
               "Locking repository acme/api. Security Lead approval required.", 5),
        Intent("log_alert", ["alert", "suspicious", "log", "detect", "uyari"],
               "slack-prod", "send_message",
               lambda t: {"channel": "#security", "message": t[:200]},
               "Security alert logged to #security channel. Auto-processed.", 0),
    ]

    # ── Dependency Update Agent ──────────────────────────────────────────
    agents["dependency_update"] = [
        Intent("major_update", ["major", "breaking", "buyuk"],
               "github-prod", "merge_pr",
               lambda t: {"package": _extract_name(t, "update") or "webpack",
                          "from_version": "5.91.0", "to_version": "6.0.0", "update_type": "major"},
               "BREAKING update: {package} {from_version} -> {to_version}. Full team approval required.", 10),
        Intent("minor_update", ["minor", "kucuk"],
               "github-prod", "merge_pr",
               lambda t: {"package": _extract_name(t, "update") or "react",
                          "from_version": "18.2.0", "to_version": "18.3.0", "update_type": "minor"},
               "Minor update: {package} {from_version} -> {to_version}. Lead Engineer approval.", 5),
        Intent("update", ["update", "upgrade", "guncelle", "patch", "dependency"],
               "github-prod", "merge_pr",
               lambda t: {"package": _extract_name(t, "update") or "lodash",
                          "from_version": "4.17.20", "to_version": "4.17.21", "update_type": "patch"},
               "Patch update: {package} {from_version} -> {to_version}. Auto-merge.", 0),
    ]

    # ── Database Migration Agent ─────────────────────────────────────────
    agents["db_migration"] = [
        Intent("prod_migration", ["production", "prod", "canli"],
               "github-prod", "deploy",
               lambda t: {"type": "migration", "env": "production", "migration_name": "alter_schema",
                          "description": t[:60]},
               "Running PRODUCTION migration: {migration_name}. DBA + CTO required.", 10),
        Intent("staging_migration", ["staging", "test"],
               "github-prod", "deploy",
               lambda t: {"type": "migration", "env": "staging", "migration_name": "alter_orders"},
               "Running staging migration: {migration_name}. DBA approval needed.", 5),
        Intent("dev_migration", ["migrate", "migration", "schema", "index", "alter", "drop", "add column"],
               "github-prod", "deploy",
               lambda t: {"type": "migration", "env": "dev", "migration_name": "add_index"},
               "Running dev migration: {migration_name}. Auto-approved.", 0),
    ]

    # ── API Key Rotation Agent ───────────────────────────────────────────
    agents["api_key_rotation"] = [
        Intent("third_party", ["third.party", "partner", "external", "dis"],
               "github-prod", "deploy",
               lambda t: {"type": "key_rotation", "service": "partner-api", "scope": "third_party", "provider": "PaymentCo"},
               "Rotating third-party partner key. CTO + Security Lead required.", 10),
        Intent("emergency", ["emergency", "acil", "compromised", "leaked", "exposed"],
               "github-prod", "deploy",
               lambda t: {"type": "key_rotation", "service": "aws", "urgency": "emergency",
                          "reason": t[:60]},
               "EMERGENCY key rotation for {service}. Security Lead approval.", 5),
        Intent("rotate", ["rotate", "dondur", "key", "credential", "anahtar"],
               "github-prod", "deploy",
               lambda t: {"type": "key_rotation", "service": "stripe", "urgency": "scheduled"},
               "Scheduled key rotation for {service}. Auto-approved.", 0),
    ]

    # ── Compliance Audit Agent ───────────────────────────────────────────
    agents["compliance_audit"] = [
        Intent("regulatory", ["regulatory", "regulator", "file report", "resmi", "duzenleyici"],
               "gmail-prod", "send_email",
               lambda t: {"type": "regulatory_filing", "authority": "DPA Ireland",
                          "subject": "Mandatory notification"},
               "Filing regulatory report to {authority}. Legal + CEO required.", 10),
        Intent("violation", ["violation", "ihlal", "breach", "non-compliance"],
               "gmail-prod", "send_email",
               lambda t: {"type": "violation_report", "framework": "GDPR",
                          "description": t[:80], "severity": "medium"},
               "Reporting {framework} violation: {description}. Compliance Officer review.", 5),
        Intent("audit", ["audit", "check", "scan", "denetim", "kontrol"],
               "slack-prod", "send_message",
               lambda t: {"channel": "#compliance", "message": "Audit pass: all controls green"},
               "Running compliance audit. Auto-approved.", 0),
    ]

    # ── Recruitment Agent ────────────────────────────────────────────────
    agents["recruitment"] = [
        Intent("salary_package", ["salary package", "equity", "maas paketi", "compensation"],
               "gmail-prod", "send_email",
               lambda t: {"type": "salary_package", "candidate": _extract_email(t) or "senior@example.com",
                          "salary": _extract_amount(t) or 220000, "equity": "0.5%"},
               "Preparing salary package: ${salary} + {equity} equity. HR + CFO approval required.", 10),
        Intent("termination", ["terminate", "fire", "isten cikar", "dismissal"],
               "gmail-prod", "send_email",
               lambda t: {"type": "termination", "recipient": _extract_email(t) or "employee@example.com",
                          "subject": "Employment Termination"},
               "SENSITIVE: Termination notice for {recipient}. HR + CEO required.", 10),
        Intent("offer", ["offer", "teklif", "hire"],
               "gmail-prod", "send_email",
               lambda t: {"type": "offer_letter", "recipient": _extract_email(t) or "candidate@example.com",
                          "subject": f"Offer: ${_extract_amount(t) or 180000}"},
               "Sending offer letter to {recipient}. HR Manager approval.", 5),
        Intent("interview", ["interview", "mulakat", "invite", "schedule"],
               "gmail-prod", "send_email",
               lambda t: {"type": "invite", "recipient": _extract_email(t) or "candidate@example.com",
                          "subject": "Interview Invitation"},
               "Sending interview invite to {recipient}. Auto-approved.", 0),
    ]

    # ── Access Provisioning Agent ────────────────────────────────────────
    agents["access_provisioning"] = [
        Intent("financial_access", ["financial", "finance", "finans"],
               "github-prod", "add_member",
               lambda t: {"username": _extract_email(t) or "finance-lead", "access_level": "financial"},
               "Granting financial system access to {username}. CFO + CTO required.", 10),
        Intent("admin_access", ["admin", "yonetici"],
               "github-prod", "add_member",
               lambda t: {"username": _extract_email(t) or "senior-dev", "role": "admin", "access_level": "admin"},
               "Granting admin access to {username}. CTO approval required.", 5),
        Intent("revoke", ["revoke", "remove", "iptal", "kaldir", "depart"],
               "github-prod", "remove_member",
               lambda t: {"username": _extract_email(t) or "departed", "org": "acme-corp", "reason": "Employment ended"},
               "Revoking all access for {username}. Auto-processed.", 8),
        Intent("grant_access", ["access", "erisim", "grant", "provision"],
               "github-prod", "add_member",
               lambda t: {"username": _extract_email(t) or "new-hire", "access_level": "standard"},
               "Granting standard access to {username}. IT Manager approval.", 0),
    ]

    # ── Leave Management Agent ───────────────────────────────────────────
    agents["leave_management"] = [
        Intent("critical_leave", ["critical", "launch", "kritik", "important period"],
               "calendar-prod", "block_time",
               lambda t: {"employee": _extract_email(t) or "lead@company.com",
                          "days": _extract_number(t) or 3, "is_critical_period": True, "reason": t[:60]},
               "Leave during critical period: {days} days. Manager + CEO required.", 10),
        Intent("long_leave", ["sabbatical", "uzun izin", "month", "3 month"],
               "calendar-prod", "block_time",
               lambda t: {"employee": _extract_email(t) or "employee@company.com",
                          "days": _extract_number(t) or 60},
               "Long leave request: {days} days. HR Manager approval.", 5),
        Intent("leave", ["leave", "izin", "off", "vacation", "tatil", "day off"],
               "calendar-prod", "block_time",
               lambda t: {
                   "employee": _extract_email(t) or "alice@company.com",
                   "days": _extract_number(t) or 1,
                   "start_date": "2026-04-03",
               },
               "Leave request: {days} day(s) starting {start_date}.", 0),
    ]

    # ── Contractor Onboarding Agent ──────────────────────────────────────
    agents["contractor_onboarding"] = [
        Intent("large_contract", ["large contract", "buyuk sozlesme", "$10k", "$15k", "$20k"],
               "stripe-prod", "charge",
               lambda t: {"type": "contractor_agreement", "contractor": _extract_email(t) or "agency@consulting.com",
                          "amount_usd": _extract_amount(t) or 15000},
               "Setting up large contract ${amount_usd}/mo with {contractor}. Legal + CEO required.", 10),
        Intent("payment", ["payment", "odeme", "agreement", "rate"],
               "stripe-prod", "charge",
               lambda t: {"type": "contractor_agreement", "contractor": _extract_email(t) or "dev@freelance.com",
                          "amount_usd": _extract_amount(t) or 5000},
               "Setting up payment agreement: ${amount_usd}/mo for {contractor}. Legal review.", 5),
        Intent("nda", ["nda", "gizlilik", "confidentiality"],
               "gmail-prod", "send_email",
               lambda t: {"type": "nda", "recipient": _extract_email(t) or "contractor@freelance.com",
                          "subject": "NDA Agreement"},
               "Sending NDA to {recipient}. Auto-approved.", 0),
        Intent("onboard", ["onboard", "contractor", "freelancer"],
               "gmail-prod", "send_email",
               lambda t: {"type": "nda", "recipient": _extract_email(t) or "contractor@freelance.com",
                          "subject": "Welcome - Onboarding"},
               "Starting contractor onboarding for {recipient}.", 0),
    ]

    # ── Performance Review Agent ─────────────────────────────────────────
    agents["performance_review"] = [
        Intent("salary_increase", ["salary increase", "raise", "maas artisi", "zam"],
               "stripe-prod", "charge",
               lambda t: {"type": "salary_increase", "employee": _extract_email(t) or "bob@company.com",
                          "current": 150000, "new_salary": _extract_amount(t) or 175000},
               "Processing salary increase to ${new_salary}. HR + CFO required.", 10),
        Intent("promote", ["promote", "promotion", "terfi"],
               "gmail-prod", "send_email",
               lambda t: {"type": "promotion", "employee": _extract_email(t) or "alice@company.com",
                          "new_title": "Staff Engineer"},
               "Recommending promotion for {employee} to {new_title}. HR + Manager required.", 5),
        Intent("review", ["review", "degerlendirme", "performance", "form"],
               "gmail-prod", "send_email",
               lambda t: {"type": "review_form", "recipient": "team@company.com",
                          "subject": "Quarterly Performance Review"},
               "Sending review forms. Auto-approved.", 0),
    ]

    # ── Support Escalation Agent ─────────────────────────────────────────
    agents["support_escalation"] = [
        Intent("compensation", ["compensation", "tazminat", "$5000", "refund", "large"],
               "stripe-prod", "refund",
               lambda t: {"type": "compensation", "amount_usd": _extract_amount(t) or 5000,
                          "customer": _extract_email(t) or "enterprise@bigcorp.com", "reason": t[:60]},
               "Processing ${amount_usd} compensation for {customer}. CFO + Legal required.", 10),
        Intent("vip", ["vip", "enterprise", "priority", "important"],
               "salesforce-prod", "update_case",
               lambda t: {"customer_tier": "vip", "customer": _extract_email(t) or "enterprise@bigcorp.com",
                          "subject": t[:60]},
               "Escalating VIP complaint from {customer}. CS Manager approval.", 5),
        Intent("complaint", ["complaint", "issue", "problem", "sikayet", "sorun", "help"],
               "gmail-prod", "send_email",
               lambda t: {"type": "standard", "customer": _extract_email(t) or "user@example.com",
                          "subject": t[:60]},
               "Handling customer complaint. Auto-responding.", 0),
    ]

    # ── Account Takeover Agent ───────────────────────────────────────────
    agents["account_takeover"] = [
        Intent("ban", ["ban", "permanent", "kalici", "yasak"],
               "salesforce-prod", "update_case",
               lambda t: {"type": "permanent_ban", "account_id": "ACC-67890", "reason": t[:60]},
               "Permanent account ban. Security + Legal required.", 10),
        Intent("freeze", ["freeze", "dondur", "lock account", "suspend"],
               "salesforce-prod", "update_case",
               lambda t: {"type": "freeze_account", "account_id": "ACC-12345", "reason": t[:60]},
               "Freezing account ACC-12345. Security Lead approval.", 5),
        Intent("alert", ["alert", "suspicious", "detect", "unusual", "suphe"],
               "slack-prod", "send_message",
               lambda t: {"channel": "#security", "message": t[:200]},
               "Security alert logged. Auto-processed.", 0),
    ]

    # ── SLA Breach Agent ─────────────────────────────────────────────────
    agents["sla_breach"] = [
        Intent("large_credit", ["large", "major", "buyuk", "$5000", "$10000", "$50000"],
               "stripe-prod", "credit",
               lambda t: {"type": "sla_credit", "amount_usd": _extract_amount(t) or 50000,
                          "customer": _extract_email(t) or "enterprise@bigcorp.com"},
               "Major SLA compensation: ${amount_usd}. CFO + Legal required.", 10),
        Intent("credit", ["credit", "kredi", "refund", "iade"],
               "stripe-prod", "credit",
               lambda t: {"type": "sla_credit", "amount_usd": _extract_amount(t) or 2000,
                          "customer": _extract_email(t) or "client@example.com"},
               "Issuing SLA credit: ${amount_usd}. CS Manager approval.", 5),
        Intent("notify", ["notify", "breach", "sla", "downtime", "outage", "bildir"],
               "gmail-prod", "send_email",
               lambda t: {"type": "notification", "customer": _extract_email(t) or "client@example.com",
                          "subject": "Service Level Update"},
               "Sending SLA breach notification. Auto-approved.", 0),
    ]

    # ── Patient Data Sharing Agent ───────────────────────────────────────
    agents["patient_data"] = [
        Intent("insurance_share", ["insurance", "sigorta"],
               "gdrive-prod", "share_file",
               lambda t: {"patient_id": "PAT-001", "recipient_type": "insurance",
                          "insurance_company": "HealthCare Inc"},
               "Sharing records with insurance. Patient Rep + Doctor required.", 10),
        Intent("external_share", ["external", "clinic", "hospital", "dis", "klinik"],
               "gdrive-prod", "share_file",
               lambda t: {"patient_id": "PAT-001", "recipient_type": "external_clinic",
                          "clinic": "City Hospital"},
               "Sharing records with external clinic. Doctor approval.", 5),
        Intent("share", ["share", "paylas", "record", "dosya", "patient"],
               "gdrive-prod", "share_file",
               lambda t: {"patient_id": "PAT-001", "recipient_type": "own_doctor", "doctor": "Dr. Smith"},
               "Sharing with patient's own doctor. Auto-approved.", 0),
    ]

    # ── Medical Supply Agent ─────────────────────────────────────────────
    agents["medical_supply"] = [
        Intent("device", ["device", "cihaz", "equipment", "machine", "$20000", "$50000"],
               "stripe-prod", "charge",
               lambda t: {"type": "medical_supply", "amount_usd": _extract_amount(t) or 50000,
                          "item": "Portable Ultrasound System"},
               "Ordering medical device: {item} (${amount_usd}). Chief Doctor + CFO required.", 10),
        Intent("supply", ["supply", "order", "siparis", "malzeme", "glove", "mask"],
               "stripe-prod", "charge",
               lambda t: {"type": "medical_supply", "amount_usd": _extract_amount(t) or 200,
                          "item": t[:40], "category": "consumable"},
               "Ordering supplies: {item} (${amount_usd}).", 0),
    ]

    # ── Prescription Refill Agent ────────────────────────────────────────
    agents["prescription_refill"] = [
        Intent("dosage_change", ["dosage", "change", "doz", "increase", "decrease"],
               "gmail-prod", "send_email",
               lambda t: {"type": "dosage_change", "medication": "Lisinopril",
                          "old_dosage": "10mg", "new_dosage": "20mg",
                          "patient": _extract_email(t) or "patient@example.com"},
               "Dosage change: {medication} {old_dosage} -> {new_dosage}. Doctor + Pharmacist.", 10),
        Intent("controlled", ["controlled", "kontrol", "adderall", "opioid", "narcotic"],
               "gmail-prod", "send_email",
               lambda t: {"type": "controlled_refill", "medication": "Adderall", "dosage": "20mg",
                          "patient": _extract_email(t) or "patient@example.com"},
               "Controlled substance refill: {medication} {dosage}. Doctor approval required.", 5),
        Intent("refill", ["refill", "yenile", "prescription", "ilac", "medication"],
               "gmail-prod", "send_email",
               lambda t: {"type": "routine_refill", "medication": "Metformin", "dosage": "500mg",
                          "patient": _extract_email(t) or "patient@example.com"},
               "Routine refill: {medication} {dosage}. Auto-processed.", 0),
    ]

    # ── Research Data Agent ──────────────────────────────────────────────
    agents["research_data"] = [
        Intent("external_share", ["external", "institution", "share with", "dis kurum"],
               "gdrive-prod", "share_file",
               lambda t: {"data_type": "external_share", "institution": "MIT Research Lab",
                          "study_id": "COLLAB-003"},
               "Sharing data with {institution}. Ethics Board + Chief Doctor required.", 10),
        Intent("patient_data", ["patient", "identifiable", "clinical trial", "hasta"],
               "gdrive-prod", "share_file",
               lambda t: {"data_type": "patient_level", "study_id": "TRIAL-007",
                          "researcher": _extract_email(t) or "dr.smith@hospital.edu"},
               "Accessing patient-level data for {study_id}. Ethics Board approval.", 5),
        Intent("data", ["data", "veri", "access", "dataset", "study", "arastirma"],
               "gdrive-prod", "share_file",
               lambda t: {"data_type": "anonymized", "study_id": "STUDY-042",
                          "researcher": _extract_email(t) or "researcher@edu"},
               "Accessing anonymized dataset {study_id}. Auto-approved.", 0),
    ]

    # ── Grade Override Agent ─────────────────────────────────────────────
    agents["grade_override"] = [
        Intent("final_override", ["final", "override", "genel not"],
               "gsheets-prod", "update_sheet",
               lambda t: {"type": "final_override", "student": "STU-9012", "course": "PHY301",
                          "current_grade": "C", "new_grade": "B-"},
               "Final grade override: {course} {current_grade} -> {new_grade}. Teacher + Dept Head.", 10),
        Intent("appeal", ["appeal", "itiraz", "raise grade", "not yukselt"],
               "gsheets-prod", "update_sheet",
               lambda t: {"type": "grade_appeal", "student": "STU-5678", "course": "MATH201",
                          "current_grade": "B", "new_grade": "B+"},
               "Grade appeal: {course} {current_grade} -> {new_grade}. Teacher approval.", 5),
        Intent("fix", ["fix", "error", "hata", "correct", "duzelt", "admin"],
               "gsheets-prod", "update_sheet",
               lambda t: {"type": "admin_error", "student": "STU-1234", "course": "CS101",
                          "current_grade": 72, "new_grade": 78},
               "Fixing administrative error: {course} {current_grade} -> {new_grade}. Auto.", 0),
    ]

    # ── Scholarship Agent ────────────────────────────────────────────────
    agents["scholarship"] = [
        Intent("full", ["full scholarship", "tam burs", "$40000"],
               "stripe-prod", "payout",
               lambda t: {"type": "full_scholarship", "amount_usd": _extract_amount(t) or 40000,
                          "student": _extract_email(t) or "exceptional@university.edu"},
               "Full scholarship ${amount_usd}/yr for {student}. Rector + Committee.", 10),
        Intent("award", ["award", "scholarship", "burs", "grant"],
               "stripe-prod", "payout",
               lambda t: {"type": "scholarship", "amount_usd": _extract_amount(t) or 5000,
                          "student": _extract_email(t) or "top@university.edu"},
               "Scholarship award: ${amount_usd} for {student}. Committee review.", 5),
        Intent("application", ["apply", "application", "basvuru", "accept"],
               "gmail-prod", "send_email",
               lambda t: {"type": "application", "student": _extract_email(t) or "applicant@university.edu",
                          "subject": "Application received"},
               "Application recorded. Confirmation sent. Auto.", 0),
    ]

    # ── Research Grant Agent ─────────────────────────────────────────────
    agents["research_grant"] = [
        Intent("large_grant", ["large", "collaboration", "external", "$50k", "$75k", "buyuk"],
               "stripe-prod", "charge",
               lambda t: {"type": "grant", "amount_usd": _extract_amount(t) or 75000,
                          "purpose": t[:60]},
               "Large grant expenditure: ${amount_usd}. Rector + External Board required.", 10),
        Intent("medium_grant", ["conference", "sponsorship", "medium"],
               "stripe-prod", "charge",
               lambda t: {"type": "grant", "amount_usd": _extract_amount(t) or 25000,
                          "purpose": t[:60]},
               "Grant expenditure: ${amount_usd}. Rector approval.", 5),
        Intent("grant", ["grant", "spend", "hibe", "fon", "lab", "equipment"],
               "stripe-prod", "charge",
               lambda t: {"type": "grant", "amount_usd": _extract_amount(t) or 3000,
                          "purpose": t[:60]},
               "Grant expenditure: ${amount_usd}.", 0),
    ]

    # ── Contract Signing Agent ───────────────────────────────────────────
    agents["contract_signing"] = [
        Intent("partnership", ["partnership", "ortaklik", "strategic"],
               "gmail-prod", "send_email",
               lambda t: {"type": "partnership", "party": "BigTech Inc",
                          "subject": "Strategic Partnership Agreement"},
               "Partnership agreement. CEO + Legal required.", 10),
        Intent("service_agreement", ["service agreement", "servis", "contract", "sozlesme"],
               "gmail-prod", "send_email",
               lambda t: {"type": "service_agreement", "party": _extract_email(t) or "vendor@example.com",
                          "subject": "Service Agreement"},
               "Service agreement for {party}. Legal review.", 5),
        Intent("nda", ["nda", "gizlilik", "confidential"],
               "gmail-prod", "send_email",
               lambda t: {"type": "nda", "party": _extract_email(t) or "partner@example.com",
                          "subject": "Mutual NDA"},
               "Sending NDA to {party}. Auto-approved.", 0),
    ]

    # ── GDPR Request Agent ───────────────────────────────────────────────
    agents["gdpr_request"] = [
        Intent("bulk_delete", ["bulk", "toplu", "mass delete", "500"],
               "github-prod", "deploy",
               lambda t: {"type": "gdpr_bulk_delete", "count": _extract_number(t) or 500,
                          "reason": "Data retention cleanup"},
               "Bulk GDPR delete: {count} records. CTO + Privacy Officer required.", 10),
        Intent("delete", ["delete", "sil", "remove data", "erase", "purge"],
               "github-prod", "deploy",
               lambda t: {"type": "gdpr_delete", "user_email": _extract_email(t) or "user@example.com"},
               "Deleting data for {user_email}. Privacy Officer approval.", 5),
        Intent("request", ["gdpr", "request", "talep", "data request"],
               "slack-prod", "send_message",
               lambda t: {"channel": "#privacy", "message": f"GDPR request: {t[:100]}"},
               "GDPR request logged. Auto-processed.", 0),
    ]

    # ── IP Filing Agent ──────────────────────────────────────────────────
    agents["ip_filing"] = [
        Intent("international", ["international", "pct", "uluslararasi", "worldwide"],
               "gmail-prod", "send_email",
               lambda t: {"type": "international_filing", "title": t[:60],
                          "jurisdictions": ["US", "EU", "JP"]},
               "International patent (PCT) filing. CEO + Legal required.", 10),
        Intent("domestic", ["patent", "file", "domestic", "basvuru"],
               "gmail-prod", "send_email",
               lambda t: {"type": "domestic_filing", "title": t[:60], "jurisdiction": "US"},
               "Domestic patent filing. Legal review.", 5),
        Intent("draft", ["draft", "prepare", "taslak", "idea", "invention"],
               "slack-prod", "send_message",
               lambda t: {"channel": "#ip", "message": f"Patent draft: {t[:100]}"},
               "Preparing patent draft. Auto-processed.", 0),
    ]

    # ── Maintenance Request Agent ────────────────────────────────────────
    agents["maintenance_request"] = [
        Intent("emergency", ["emergency", "acil", "burst", "flood", "yangin"],
               "stripe-prod", "charge",
               lambda t: {"type": "maintenance", "amount_usd": _extract_amount(t) or 2000,
                          "description": "EMERGENCY: " + t[:60], "is_emergency": True},
               "EMERGENCY repair: {description}. Auto-approved (no blackout).", 10),
        Intent("repair", ["repair", "fix", "replace", "maintenance", "bakim", "onarim"],
               "stripe-prod", "charge",
               lambda t: {"type": "maintenance", "amount_usd": _extract_amount(t) or 500,
                          "description": t[:60]},
               "Maintenance request: {description} (${amount_usd}).", 0),
    ]

    # ── Tenant Screening Agent ───────────────────────────────────────────
    agents["tenant_screening"] = [
        Intent("criminal", ["criminal", "sabika", "background"],
               "salesforce-prod", "create_ticket",
               lambda t: {"check_type": "criminal_check", "applicant": "Applicant",
                          "unit": "Apt 2C"},
               "Criminal background check for {applicant}. Manager + Legal required.", 10),
        Intent("eviction", ["eviction", "tahliye", "prior eviction"],
               "salesforce-prod", "create_ticket",
               lambda t: {"check_type": "eviction_history", "applicant": "Applicant",
                          "unit": "Apt 5B"},
               "Eviction history review. Property Manager approval.", 5),
        Intent("screen", ["screen", "check", "credit", "applicant", "tenant", "kiraci"],
               "salesforce-prod", "create_ticket",
               lambda t: {"check_type": "credit", "applicant": "Applicant", "unit": "Apt 3A"},
               "Running credit check. Auto-processed.", 0),
    ]

    # ── Content Moderation Agent ─────────────────────────────────────────
    agents["content_moderation"] = [
        Intent("ban", ["ban", "yasak", "permanent"],
               "slack-prod", "send_message",
               lambda t: {"type": "account_ban", "account_id": "USER-99999",
                          "reason": t[:60]},
               "Account ban for {account_id}. Sr. Moderator + Legal required.", 10),
        Intent("flag", ["flag", "suspicious", "review", "suphe", "incele"],
               "slack-prod", "send_message",
               lambda t: {"type": "suspicious_content", "content_id": "POST-67890",
                          "reason": t[:60]},
               "Flagging content for review. Moderator approval.", 5),
        Intent("spam", ["spam", "remove", "delete", "kaldir"],
               "slack-prod", "send_message",
               lambda t: {"channel": "#moderation", "message": f"Spam removed: {t[:60]}"},
               "Spam removed. Auto-processed.", 0),
    ]

    # ── Licensing Agent ──────────────────────────────────────────────────
    agents["licensing"] = [
        Intent("major_deal", ["major", "deal", "media deal", "$100k", "$250k", "buyuk"],
               "stripe-prod", "charge",
               lambda t: {"type": "major_deal", "amount_usd": _extract_amount(t) or 250000,
                          "licensee": "Global Media Inc"},
               "Major media deal: ${amount_usd}. CEO + Legal required.", 10),
        Intent("commercial", ["commercial", "ticari", "business license"],
               "stripe-prod", "charge",
               lambda t: {"type": "commercial_license", "amount_usd": _extract_amount(t) or 5000,
                          "licensee": _extract_email(t) or "MediaCorp Ltd"},
               "Commercial license for {licensee}: ${amount_usd}. Legal review.", 5),
        Intent("personal", ["personal", "license", "lisans", "kisisel"],
               "stripe-prod", "charge",
               lambda t: {"type": "personal_license", "amount_usd": 29,
                          "licensee": _extract_email(t) or "user@example.com"},
               "Personal license issued. Auto-approved.", 0),
    ]

    # ── Environmental Incident Agent ─────────────────────────────────────
    agents["environmental_incident"] = [
        Intent("major", ["major", "containment", "breach", "buyuk", "ciddi", "critical"],
               "gmail-prod", "send_email",
               lambda t: {"type": "major_incident", "incident_type": "Containment breach",
                          "location": "Building C"},
               "MAJOR incident reported. CEO + Environmental Officer required.", 10),
        Intent("spill", ["spill", "leak", "sizinti", "dokuntu"],
               "slack-prod", "send_message",
               lambda t: {"channel": "#safety", "message": f"Minor spill: {t[:100]}"},
               "Minor spill reported. Auto-notify activated.", 5),
        Intent("monitor", ["monitor", "reading", "check", "olcum", "log"],
               "slack-prod", "send_message",
               lambda t: {"channel": "#environment", "message": "Readings: all parameters OK"},
               "Environmental monitoring logged. Auto.", 0),
    ]

    # ── Renewable Energy Agent ───────────────────────────────────────────
    agents["renewable_energy"] = [
        Intent("ppa", ["ppa", "long-term", "agreement", "uzun vadeli", "sozlesme"],
               "stripe-prod", "charge",
               lambda t: {"type": "ppa_agreement", "amount_usd": _extract_amount(t) or 500000,
                          "years": _extract_number(t) or 5, "annual_mwh": 5000},
               "PPA agreement: {years}-year, ${amount_usd}. CEO + CFO required.", 10),
        Intent("purchase", ["purchase", "buy", "credit", "energy", "solar", "wind", "enerji"],
               "stripe-prod", "charge",
               lambda t: {
                   "type": "energy_purchase",
                   "amount_usd": _extract_amount(t) or 8000,
                   "quantity": (_extract_amount(t) or 8000) // 80,
                   "source": "solar" if _kw_match(t, ["solar", "gunes"]) else "wind",
               },
               "Purchasing {quantity} MWh {source} credits (${amount_usd}).", 0),
    ]

    return agents


# ── Singleton ──────────────────────────────────────────────────────────────────
_AGENT_INTENTS: dict[str, list[Intent]] | None = None


def get_agent_intents() -> dict[str, list[Intent]]:
    global _AGENT_INTENTS
    if _AGENT_INTENTS is None:
        _AGENT_INTENTS = _build_agent_intents()
    return _AGENT_INTENTS


# ── Public API ─────────────────────────────────────────────────────────────────

GREETINGS = ["hi", "hello", "hey", "merhaba", "selam", "nasilsin", "nasil"]
HELP_WORDS = ["help", "yardim", "what can", "ne yapabilir", "neler", "commands", "options"]


def get_suggestions(agent_id: str) -> list[str]:
    """Return example prompts for an agent."""
    intents = get_agent_intents().get(agent_id, [])
    suggestions = []
    for intent in sorted(intents, key=lambda i: i.priority, reverse=True):
        tpl = intent.response_template
        # Create a short example from the intent name
        suggestions.append(intent.name.replace("_", " ").title())
    return suggestions[:6]


def process_message(agent_id: str, message: str, agent_title: str = "") -> dict[str, Any]:
    """
    Process a user message and return a structured response.

    Returns: {
        "response": str,           # Agent's text response
        "action": {...} | None,    # Action to execute via ApprovalKit
        "suggestions": [...],      # Next suggested actions
        "type": "chat" | "action"  # Response type
    }
    """
    text = message.strip()
    lower = text.lower()

    # Handle greetings
    if any(lower.startswith(g) or lower == g for g in GREETINGS):
        return {
            "response": f"Hello! I'm the {agent_title}. How can I help you today?\n\nHere are some things I can do:",
            "action": None,
            "suggestions": get_suggestions(agent_id),
            "type": "chat",
        }

    # Handle help
    if any(w in lower for w in HELP_WORDS):
        suggestions = get_suggestions(agent_id)
        return {
            "response": f"I can help you with:\n\n" + "\n".join(f"  - {s}" for s in suggestions) + "\n\nJust type what you need!",
            "action": None,
            "suggestions": suggestions,
            "type": "chat",
        }

    # Match intents
    intents = get_agent_intents().get(agent_id, [])
    matched: list[tuple[int, Intent]] = []

    for intent in intents:
        score = 0
        for kw in intent.keywords:
            if kw.lower() in lower:
                score += len(kw)  # Longer keyword matches score higher
        if score > 0:
            matched.append((score + intent.priority * 2, intent))

    if not matched:
        # No match - provide suggestions
        return {
            "response": f"I'm not sure what you'd like me to do. Could you be more specific?\n\nHere are some things I can help with:",
            "action": None,
            "suggestions": get_suggestions(agent_id),
            "type": "chat",
        }

    # Pick best match
    matched.sort(key=lambda x: x[0], reverse=True)
    _, best = matched[0]

    # Build params
    params = best.param_builder(text)

    # Format response
    try:
        response = best.response_template.format(**params)
    except (KeyError, IndexError):
        response = best.response_template

    return {
        "response": response,
        "action": {
            "connection": best.connection,
            "action": best.action,
            "params": params,
        },
        "suggestions": get_suggestions(agent_id),
        "type": "action",
    }
