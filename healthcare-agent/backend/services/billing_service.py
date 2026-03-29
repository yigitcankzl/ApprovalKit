"""
Billing Service — Invoice processing with amount-based step-up approvals.

Approval flows:
  < $500:   auto-approve (no rule matches)
  $500+:    finance manager (specific)
  $10,000+: finance manager + hospital director (step-up → all_of_n)
  $25,000+: finance manager + hospital director + CMO (all_of_n, highest priority)
  Appeal:   doctor + finance (all_of_n)
"""
import uuid
import logging
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.models.billing import BillingRecord
from backend.models.patient import Patient
from backend.models.activity import ActivityLog
from backend.services.approval_gateway import ApprovalGateway, ApprovalDenied
from backend.services.notification_service import NotificationService

logger = logging.getLogger("healthcare.billing")


def _invoice_number(count: int) -> str:
    return f"INV-{count + 1:06d}"


class BillingService:

    @staticmethod
    async def create_billing(db: AsyncSession, data: dict) -> dict:
        patient = await db.get(Patient, uuid.UUID(data["patient_id"]))
        if not patient:
            raise ValueError("Patient not found")

        count = await db.scalar(select(func.count()).select_from(BillingRecord))
        invoice_number = _invoice_number(count or 0)

        amount = Decimal(str(data["amount"]))
        insurance_covered = Decimal(str(data.get("insurance_covered", 0)))
        patient_resp = amount - insurance_covered

        record = BillingRecord(
            id=uuid.uuid4(),
            invoice_number=invoice_number,
            patient_id=patient.id,
            description=data["description"],
            procedure_code=data.get("procedure_code"),
            amount=amount,
            insurance_covered=insurance_covered,
            patient_responsibility=patient_resp,
            notes=data.get("notes"),
            status="pending",
        )
        db.add(record)
        await db.flush()

        patient_name = f"{patient.first_name} {patient.last_name}"

        try:
            result = await ApprovalGateway.approve_billing(
                invoice_number=invoice_number,
                patient_name=patient_name,
                description=data["description"],
                amount=float(amount),
            )

            record.status = "approved"
            record.approval_job_id = result.get("job_id")

            # Send insurance claim via email
            if patient.insurance:
                await NotificationService.send_email(
                    recipient=patient.insurance.contact_email if hasattr(patient, 'insurance') and patient.insurance else "claims@insurance.com",
                    subject=f"Insurance Claim — {invoice_number}",
                    body=(
                        f"Claim for patient: {patient_name}\n"
                        f"Invoice: {invoice_number}\n"
                        f"Amount: ${amount:,.2f}\n"
                        f"Procedure: {data['description']}\n"
                    ),
                    email_type="insurance_claim",
                )

            # Slack alert for large bills
            if float(amount) >= 10000:
                await NotificationService.alert_billing(
                    invoice_number=invoice_number,
                    amount=float(amount),
                    description=data["description"],
                )

            severity = "warning" if float(amount) >= 10000 else "info"
            db.add(ActivityLog(
                event_type="billing_approved",
                category="billing",
                title=f"Invoice {invoice_number}: ${amount:,.2f}",
                description=(
                    f"Billing approved for {patient_name}. "
                    f"{'Step-up escalation applied.' if float(amount) >= 10000 else 'Standard approval.'}"
                ),
                severity=severity,
                entity_type="billing",
                entity_id=str(record.id),
                approval_job_id=record.approval_job_id,
                extra_data={"amount": float(amount), "patient_mrn": patient.mrn},
            ))

        except ApprovalDenied as e:
            record.status = "denied"
            record.approval_job_id = e.job_id
            db.add(ActivityLog(
                event_type="billing_denied",
                category="billing",
                title=f"Invoice {invoice_number} Denied",
                description=f"Billing ${amount:,.2f} denied: {e.status}",
                severity="warning",
                entity_type="billing",
                entity_id=str(record.id),
            ))

        await db.commit()
        await db.refresh(record)
        return {"billing": record, "approval_status": record.status}

    @staticmethod
    async def file_appeal(db: AsyncSession, billing_id: str, data: dict) -> dict:
        record = await db.get(BillingRecord, uuid.UUID(billing_id))
        if not record:
            raise ValueError("Billing record not found")

        patient = await db.get(Patient, record.patient_id)
        patient_name = f"{patient.first_name} {patient.last_name}" if patient else "Unknown"

        try:
            result = await ApprovalGateway.approve_insurance_appeal(
                invoice_number=record.invoice_number,
                patient_name=patient_name,
                original_amount=float(record.amount),
                appeal_reason=data["reason"],
            )

            record.appeal_status = "approved"
            record.appeal_job_id = result.get("job_id")
            record.status = "appealed"

            # Send appeal letter
            await NotificationService.send_email(
                recipient="appeals@insurance.com",
                subject=f"Insurance Appeal — {record.invoice_number}",
                body=(
                    f"Appeal for denied claim:\n\n"
                    f"Invoice: {record.invoice_number}\n"
                    f"Patient: {patient_name}\n"
                    f"Amount: ${record.amount:,.2f}\n"
                    f"Reason for appeal: {data['reason']}\n"
                ),
                email_type="insurance_appeal",
            )

            # Alert both channels
            await NotificationService.alert_billing(
                record.invoice_number, float(record.amount),
                f"Appeal filed: {data['reason']}", "#billing",
            )

            db.add(ActivityLog(
                event_type="appeal_filed",
                category="billing",
                title=f"Appeal: {record.invoice_number}",
                description=f"Insurance appeal filed for ${record.amount:,.2f}",
                severity="warning",
                entity_type="billing",
                entity_id=str(record.id),
                approval_job_id=record.appeal_job_id,
            ))

        except ApprovalDenied as e:
            record.appeal_status = "denied"
            record.appeal_job_id = e.job_id

        await db.commit()
        await db.refresh(record)
        return {"billing": record, "appeal_status": record.appeal_status}

    @staticmethod
    async def get_billing_records(db: AsyncSession, patient_id: str | None = None, limit: int = 50, offset: int = 0):
        query = select(BillingRecord).order_by(BillingRecord.created_at.desc()).limit(limit).offset(offset)
        if patient_id:
            query = query.where(BillingRecord.patient_id == uuid.UUID(patient_id))
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_billing_stats(db: AsyncSession):
        total = await db.scalar(select(func.sum(BillingRecord.amount)).select_from(BillingRecord)) or 0
        pending = await db.scalar(
            select(func.sum(BillingRecord.amount)).where(BillingRecord.status == "pending")
        ) or 0
        approved = await db.scalar(
            select(func.sum(BillingRecord.amount)).where(BillingRecord.status == "approved")
        ) or 0
        denied_count = await db.scalar(
            select(func.count()).where(BillingRecord.status == "denied")
        ) or 0

        return {
            "total_billed": float(total),
            "pending_amount": float(pending),
            "approved_amount": float(approved),
            "denied_count": denied_count,
        }
