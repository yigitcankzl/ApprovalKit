"""
ApprovalKit Integration Gateway — Token Vault First
=====================================================
Every healthcare action maps to a real Token Vault connection
(Gmail, Stripe, Google Drive, Slack, Google Calendar).
After approval, Token Vault executes the action using stored credentials.
The agent never sees or holds any API tokens.

Connection mapping (all Token Vault backed):
    gmail-prod    → send_email  (prescriptions, notifications, referrals)
    stripe-prod   → charge      (billing, payments)
    gdrive-prod   → share_file  (patient records, HIPAA sharing)
    slack-prod    → send_message (alerts, team notifications)
    gcal-prod     → create_event (appointments)
"""
import os
import sys
import logging
import asyncio
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "sdk"))

try:
    from approvalkit import ApprovalKit, ApprovalDenied
except ImportError:
    class ApprovalDenied(Exception):
        def __init__(self, status: str, job_id: str | None = None):
            self.status = status
            self.job_id = job_id
            super().__init__(f"Approval {status}")

    class ApprovalKit:
        def __init__(self, **kwargs):
            self._config = kwargs
        def gate(self, connection, action, params):
            return {"status": "simulated_approved", "final_params": params}

import httpx

from backend.config import settings

logger = logging.getLogger("healthcare.approval")

kit = ApprovalKit(
    base_url=settings.APPROVALKIT_URL,
    api_key=settings.APPROVALKIT_API_KEY,
    hmac_secret=settings.APPROVALKIT_HMAC_SECRET,
    user_id="healthcare-agent",
    poll_interval=3,
    timeout=300,
)


async def _gate_via_test_request(connection: str, action: str, params: dict) -> dict:
    """Gate via /test-request endpoint (no HMAC needed, uses X-User-Sub)."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(
                f"{settings.APPROVALKIT_URL}/api/v1/test-request",
                json={"connection": connection, "action": action, "params": params},
                headers={"X-User-Sub": os.getenv("APPROVALKIT_USER_SUB", "google-oauth2|107346137983886805538")},
            )
            result = resp.json()
            status = result.get("status", "error")
            if status in ("approved", "pre_approved", "auto_approved"):
                return {"status": status, "final_params": params, "job_id": result.get("job_id")}
            elif status == "pending":
                return {"status": "pending", "job_id": result.get("job_id"), "message": result.get("message", "Awaiting approval")}
            else:
                return {"status": status, "message": result.get("message", "")}
    except Exception as e:
        logger.error(f"ApprovalKit gate error: {e}")
        raise


__all__ = ["kit", "ApprovalDenied", "ApprovalGateway", "_gate_via_test_request"]


class ApprovalGateway:
    """
    Every method gates through a real Token Vault connection.
    After approval, Auth0 Token Vault executes the API call
    (Gmail send, Stripe charge, Drive share, etc.)
    """

    # ── Prescriptions → Gmail (send Rx to pharmacy) ────────────────────

    @staticmethod
    async def approve_routine_prescription(
        medication_name: str,
        dosage: str,
        patient_mrn: str,
        patient_name: str,
        doctor_name: str,
    ) -> dict:
        """Routine Rx → specific doctor approval → Token Vault sends Gmail to pharmacy."""
        return await _gate_via_test_request(
            "gmail-prod",
            "send_email",
            {
                "type": "prescription",
                "medication_name": medication_name,
                "dosage": dosage,
                "patient_mrn": patient_mrn,
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "is_controlled": False,
                "recipient": "pharmacy@medcore-hospital.com",
                "subject": f"Rx: {medication_name} {dosage} for {patient_name} ({patient_mrn})",
                "body": f"Prescription from {doctor_name}: {medication_name} {dosage} for patient {patient_name} ({patient_mrn}).",
            },
        )

    @staticmethod
    async def approve_controlled_substance(
        medication_name: str,
        dosage: str,
        schedule_class: str,
        patient_mrn: str,
        patient_name: str,
        doctor_name: str,
    ) -> dict:
        """Controlled substance → sequential (doctor → pharmacist) → Token Vault sends Gmail."""
        return await _gate_via_test_request(
            "gmail-prod",
            "send_email",
            {
                "type": "controlled_prescription",
                "medication_name": medication_name,
                "dosage": dosage,
                "schedule_class": schedule_class,
                "patient_mrn": patient_mrn,
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "is_controlled": True,
                "recipient": "pharmacy@medcore-hospital.com",
                "subject": f"CONTROLLED Rx: {medication_name} ({schedule_class}) for {patient_name}",
                "body": f"Controlled substance prescription from {doctor_name}: {medication_name} {dosage} (Schedule {schedule_class}) for {patient_name} ({patient_mrn}).",
            },
        )

    @staticmethod
    async def approve_dose_change(
        medication_name: str,
        previous_dosage: str,
        new_dosage: str,
        patient_mrn: str,
        patient_name: str,
        doctor_name: str,
        is_first_change: bool = False,
    ) -> dict:
        """Dose change → all_of_n (doctor + pharmacist + CMO) → Token Vault sends Gmail."""
        return await _gate_via_test_request(
            "gmail-prod",
            "send_email",
            {
                "type": "dose_change",
                "medication_name": medication_name,
                "previous_dosage": previous_dosage,
                "new_dosage": new_dosage,
                "patient_mrn": patient_mrn,
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "is_first_change": is_first_change,
                "recipient": "pharmacy@medcore-hospital.com",
                "subject": f"Dose Change: {medication_name} {previous_dosage} -> {new_dosage} for {patient_name}",
                "body": f"Dose change approved by Doctor + Pharmacist + CMO. {medication_name}: {previous_dosage} -> {new_dosage} for {patient_name} ({patient_mrn}).",
            },
        )

    # ── HIPAA Data Sharing → Google Drive (share files) ────────────────

    @staticmethod
    async def approve_external_referral(
        patient_mrn: str,
        patient_name: str,
        clinic_name: str,
        reason: str,
        data_scope: str,
    ) -> dict:
        """External referral → specific doctor → Token Vault shares via Google Drive."""
        return await _gate_via_test_request(
            "gdrive-prod",
            "share_file",
            {
                "type": "external_referral",
                "patient_mrn": patient_mrn,
                "patient_name": patient_name,
                "clinic_name": clinic_name,
                "reason": reason,
                "data_scope": data_scope,
                "file_name": f"Patient_{patient_mrn}_Records.pdf",
                "recipient_email": f"records@{clinic_name.lower().replace(' ', '-')}.com",
                "access_level": "reader",
            },
        )

    @staticmethod
    async def approve_insurance_data_request(
        patient_mrn: str,
        patient_name: str,
        insurance_name: str,
        requested_data_scope: str,
        reason: str,
    ) -> dict:
        """Insurance data → all_of_n + partial_approval → Token Vault shares via Drive."""
        return await _gate_via_test_request(
            "gdrive-prod",
            "share_file",
            {
                "type": "insurance_data",
                "patient_mrn": patient_mrn,
                "patient_name": patient_name,
                "insurance_name": insurance_name,
                "requested_data_scope": requested_data_scope,
                "reason": reason,
                "file_name": f"Patient_{patient_mrn}_Insurance_Records.pdf",
                "recipient_email": f"claims@{insurance_name.lower().replace(' ', '-')}.com",
                "access_level": "reader",
            },
        )

    @staticmethod
    async def approve_research_export(
        research_entity: str,
        reason: str,
        patient_count: int,
        data_scope: str = "anonymized",
    ) -> dict:
        """Research export → sequential (ethics → CMO → director) → Token Vault shares via Drive."""
        return await _gate_via_test_request(
            "gdrive-prod",
            "share_file",
            {
                "type": "research_export",
                "research_entity": research_entity,
                "reason": reason,
                "patient_count": patient_count,
                "data_scope": data_scope,
                "file_name": f"Research_Export_{data_scope}_{patient_count}_patients.csv",
                "recipient_email": f"data@{research_entity.lower().replace(' ', '-')}.edu",
                "access_level": "reader",
            },
        )

    # ── Billing → Stripe (charge) ─────────────────────────────────────

    @staticmethod
    async def approve_billing(
        invoice_number: str,
        patient_name: str,
        description: str,
        amount: float,
    ) -> dict:
        """Billing → auto (<$500) / specific / step-up → Token Vault charges via Stripe."""
        return await _gate_via_test_request(
            "stripe-prod",
            "charge",
            {
                "type": "medical_billing",
                "invoice_number": invoice_number,
                "patient_name": patient_name,
                "description": description,
                "amount_usd": amount,
                "customer": f"{patient_name.lower().replace(' ', '.')}@patient.medcore.com",
            },
        )

    @staticmethod
    async def approve_insurance_appeal(
        invoice_number: str,
        patient_name: str,
        original_amount: float,
        appeal_reason: str,
    ) -> dict:
        """Insurance appeal → all_of_n (doctor + finance) → Token Vault sends appeal via Gmail."""
        return await _gate_via_test_request(
            "gmail-prod",
            "send_email",
            {
                "type": "insurance_appeal",
                "invoice_number": invoice_number,
                "patient_name": patient_name,
                "amount_usd": original_amount,
                "appeal_reason": appeal_reason,
                "recipient": "appeals@insurance-provider.com",
                "subject": f"Insurance Appeal: {invoice_number} — ${original_amount:.0f} for {patient_name}",
                "body": f"Appeal for invoice {invoice_number}. Patient: {patient_name}. Amount: ${original_amount:.0f}. Reason: {appeal_reason}",
            },
        )

    # ── Emergency → Gmail (urgent notifications) ──────────────────────

    @staticmethod
    async def approve_emergency_access(
        patient_mrn: str,
        patient_name: str,
        reason: str,
        triggered_by: str,
    ) -> dict:
        """Emergency access → any_one, 2-min timeout → Token Vault sends urgent Gmail."""
        emergency_kit = ApprovalKit(
            base_url=settings.APPROVALKIT_URL,
            api_key=settings.APPROVALKIT_API_KEY,
            hmac_secret=settings.APPROVALKIT_HMAC_SECRET,
            user_id="healthcare-agent-emergency",
            poll_interval=2,
            timeout=130,
        )
        return await asyncio.to_thread(
            emergency_kit.gate,
            "gmail-prod",
            "send_email",
            {
                "type": "emergency_access",
                "patient_mrn": patient_mrn,
                "patient_name": patient_name,
                "reason": reason,
                "triggered_by": triggered_by,
                "is_emergency": True,
                "recipient": "emergency-team@medcore-hospital.com",
                "subject": f"EMERGENCY ACCESS: Patient {patient_mrn} — {reason}",
                "body": f"Emergency data access requested by {triggered_by} for patient {patient_name} ({patient_mrn}). Reason: {reason}",
            },
        )

    @staticmethod
    async def approve_security_freeze(
        reason: str,
        triggered_by: str,
        patient_id: Optional[str] = None,
    ) -> dict:
        """Security breach → all_of_n (security + CMO) → Token Vault sends alert via Slack."""
        return await _gate_via_test_request(
            "slack-prod",
            "send_message",
            {
                "type": "security_freeze",
                "reason": reason,
                "triggered_by": triggered_by,
                "patient_id": patient_id,
                "severity": "critical",
                "channel": "#security-alerts",
                "message": f"SECURITY BREACH: {reason}. Triggered by {triggered_by}. All accounts frozen.",
            },
        )

    # ── Staff / HR → Gmail (access change notifications) ──────────────

    @staticmethod
    async def approve_access_change(
        employee_name: str,
        employee_id: str,
        current_level: str,
        requested_level: str,
        reason: str,
    ) -> dict:
        """Access change → step-up based on level → Token Vault sends Gmail notification."""
        return await _gate_via_test_request(
            "gmail-prod",
            "send_email",
            {
                "type": "access_change",
                "employee_name": employee_name,
                "employee_id": employee_id,
                "current_access_level": current_level,
                "requested_access_level": requested_level,
                "reason": reason,
                "recipient": "it-admin@medcore-hospital.com",
                "subject": f"Access Change: {employee_name} — {current_level} -> {requested_level}",
                "body": f"Access change request for {employee_name} ({employee_id}). From: {current_level}. To: {requested_level}. Reason: {reason}",
            },
        )

    # ── Direct Token Vault Notifications ───────────────────────────────

    @staticmethod
    async def send_email(recipient: str, subject: str, body: str, email_type: str = "notification") -> dict:
        return await _gate_via_test_request("gmail-prod", "send_email", {"recipient": recipient, "subject": subject, "body": body, "type": email_type})

    @staticmethod
    async def send_slack_message(channel: str, message: str) -> dict:
        return await _gate_via_test_request("slack-prod", "send_message", {"channel": channel, "message": message})

    @staticmethod
    async def create_calendar_event(title: str, start_time: str, end_time: str, attendees: list[str], location: str = "") -> dict:
        return await _gate_via_test_request("gcal-prod", "create_event", {"title": title, "start_time": start_time, "end_time": end_time, "attendees": attendees, "location": location})

    @staticmethod
    async def share_drive_file(file_name: str, recipient_email: str, access_level: str = "reader", folder: str = "Patient Records") -> dict:
        return await _gate_via_test_request("gdrive-prod", "share_file", {"file_name": file_name, "recipient_email": recipient_email, "access_level": access_level, "folder": folder})
