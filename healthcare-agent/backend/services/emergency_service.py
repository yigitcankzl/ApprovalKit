"""
Emergency Service — Critical situation handling.

Approval flows:
  Emergency data access:  any_one, 2-min timeout, no blackout
  Security breach:        all_of_n (security officer + CMO), auto-freeze
"""
import uuid
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.emergency import EmergencyEvent
from backend.models.patient import Patient
from backend.models.activity import ActivityLog
from backend.services.approval_gateway import ApprovalGateway, ApprovalDenied
from backend.services.notification_service import NotificationService

logger = logging.getLogger("healthcare.emergency")


class EmergencyService:

    @staticmethod
    async def request_emergency_access(db: AsyncSession, data: dict) -> dict:
        """
        Emergency data access — any_one approval, 2-minute timeout.
        No blackout window override. Special audit logging.
        """
        patient = await db.get(Patient, uuid.UUID(data["patient_id"]))
        if not patient:
            raise ValueError("Patient not found")

        patient_name = f"{patient.first_name} {patient.last_name}"

        event = EmergencyEvent(
            id=uuid.uuid4(),
            event_type="data_access",
            severity="high",
            patient_id=patient.id,
            triggered_by=data["triggered_by"],
            reason=data["reason"],
            status="active",
            auto_timeout_seconds=120,
        )
        db.add(event)
        await db.flush()

        # Immediate Slack alert
        await NotificationService.alert_emergency(
            patient_name=patient_name,
            patient_mrn=patient.mrn,
            reason=data["reason"],
            event_type="data_access",
        )

        try:
            result = await ApprovalGateway.approve_emergency_access(
                patient_mrn=patient.mrn,
                patient_name=patient_name,
                reason=data["reason"],
                triggered_by=data["triggered_by"],
            )

            event.status = "approved"
            event.approval_job_id = result.get("job_id")

            # Share records immediately
            await NotificationService.share_patient_records(
                patient_name=patient_name,
                patient_mrn=patient.mrn,
                recipient_email=data["triggered_by"],
                data_scope="full",
            )

            event.actions_taken = f"Patient records shared with {data['triggered_by']}"

            db.add(ActivityLog(
                event_type="emergency_access_granted",
                category="emergency",
                title=f"EMERGENCY: Data access for {patient_name}",
                description=(
                    f"Emergency data access granted for {patient_name} ({patient.mrn}). "
                    f"Requested by: {data['triggered_by']}. Reason: {data['reason']}"
                ),
                severity="critical",
                entity_type="emergency",
                entity_id=str(event.id),
                approval_job_id=event.approval_job_id,
                extra_data={
                    "patient_mrn": patient.mrn,
                    "triggered_by": data["triggered_by"],
                    "emergency_type": "data_access",
                },
            ))

        except ApprovalDenied as e:
            event.status = "timeout" if e.status == "timeout" else "denied"
            event.approval_job_id = e.job_id

            # Even on timeout, log the emergency access attempt
            db.add(ActivityLog(
                event_type="emergency_access_denied",
                category="emergency",
                title=f"EMERGENCY DENIED: {patient_name}",
                description=f"Emergency access {e.status}. Escalation may be needed.",
                severity="critical",
                entity_type="emergency",
                entity_id=str(event.id),
            ))

        await db.commit()
        await db.refresh(event)
        return {"emergency": event, "approval_status": event.status}

    @staticmethod
    async def report_security_breach(db: AsyncSession, data: dict) -> dict:
        """
        Security breach protocol:
        1. Auto-freeze affected account (immediate)
        2. Slack #security alert (immediate)
        3. Approval: security officer + CMO (all_of_n)
        4. Gmail notification to affected patient
        """
        patient = None
        patient_name = "System-wide"
        patient_mrn = "N/A"

        if data.get("patient_id"):
            patient = await db.get(Patient, uuid.UUID(data["patient_id"]))
            if patient:
                patient_name = f"{patient.first_name} {patient.last_name}"
                patient_mrn = patient.mrn
                # Auto-freeze: mark patient as restricted
                patient.status = "restricted"

        event = EmergencyEvent(
            id=uuid.uuid4(),
            event_type="security_breach",
            severity=data.get("severity", "critical"),
            patient_id=patient.id if patient else None,
            triggered_by=data["triggered_by"],
            reason=data["reason"],
            status="active",
            auto_timeout_seconds=300,
            actions_taken="Account frozen (automatic)",
        )
        db.add(event)
        await db.flush()

        # Immediate Slack security alert
        await NotificationService.alert_emergency(
            patient_name=patient_name,
            patient_mrn=patient_mrn,
            reason=data["reason"],
            event_type="security_breach",
        )

        # Request security + CMO approval
        try:
            result = await ApprovalGateway.approve_security_freeze(
                reason=data["reason"],
                triggered_by=data["triggered_by"],
                patient_id=data.get("patient_id"),
            )

            event.status = "investigating"
            event.approval_job_id = result.get("job_id")

            # Notify affected patient
            if patient:
                await NotificationService.send_email(
                    recipient=patient.email,
                    subject="Security Notice — MedCore General Hospital",
                    body=(
                        f"Dear {patient_name},\n\n"
                        f"We detected unauthorized access to your account.\n"
                        f"Your account has been temporarily restricted as a precaution.\n\n"
                        f"Our security team is investigating. We will contact you with updates.\n\n"
                        f"— MedCore General Hospital Security Team"
                    ),
                    email_type="security_alert",
                )

            db.add(ActivityLog(
                event_type="security_breach_reported",
                category="emergency",
                title=f"SECURITY BREACH: {patient_name}",
                description=(
                    f"Security breach reported. Account frozen. "
                    f"Reason: {data['reason']}. Under investigation."
                ),
                severity="critical",
                entity_type="emergency",
                entity_id=str(event.id),
                approval_job_id=event.approval_job_id,
                extra_data={
                    "patient_mrn": patient_mrn,
                    "severity": event.severity,
                    "auto_frozen": True,
                },
            ))

        except ApprovalDenied as e:
            event.status = "escalated"
            event.approval_job_id = e.job_id

        await db.commit()
        await db.refresh(event)
        return {"emergency": event, "approval_status": event.status}

    @staticmethod
    async def resolve_emergency(db: AsyncSession, event_id: str, resolved_by: str) -> dict:
        event = await db.get(EmergencyEvent, uuid.UUID(event_id))
        if not event:
            raise ValueError("Emergency event not found")

        event.status = "resolved"
        event.resolved_at = datetime.utcnow()
        event.resolved_by = resolved_by

        # Restore patient status if frozen
        if event.patient_id:
            patient = await db.get(Patient, event.patient_id)
            if patient and patient.status == "restricted":
                patient.status = "active"

        db.add(ActivityLog(
            event_type="emergency_resolved",
            category="emergency",
            title=f"Emergency Resolved: {event.event_type}",
            description=f"Resolved by {resolved_by}",
            severity="info",
            entity_type="emergency",
            entity_id=str(event.id),
        ))

        await db.commit()
        await db.refresh(event)
        return {"emergency": event}

    @staticmethod
    async def get_active_emergencies(db: AsyncSession):
        result = await db.execute(
            select(EmergencyEvent)
            .where(EmergencyEvent.status.in_(["active", "investigating", "escalated"]))
            .order_by(EmergencyEvent.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_all_emergencies(db: AsyncSession, limit: int = 50):
        result = await db.execute(
            select(EmergencyEvent).order_by(EmergencyEvent.created_at.desc()).limit(limit)
        )
        return result.scalars().all()
