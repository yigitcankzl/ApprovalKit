"""
Referral Service — HIPAA-compliant data sharing workflows.

Approval flows:
  External referral:     specific (referring doctor)
  Insurance data:        all_of_n with partial_approval (patient rep + doctor)
  Research export:       sequential (ethics board → CMO → hospital director)
"""
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.referral import Referral
from backend.models.patient import Patient
from backend.models.doctor import Doctor
from backend.models.insurance import InsuranceProvider, InsuranceRequest
from backend.models.activity import ActivityLog
from backend.services.approval_gateway import ApprovalGateway, ApprovalDenied
from backend.services.notification_service import NotificationService

logger = logging.getLogger("healthcare.referrals")


class ReferralService:

    @staticmethod
    async def create_external_referral(db: AsyncSession, data: dict) -> dict:
        """External clinic referral → doctor approval → Drive share → Gmail notify."""
        patient = await db.get(Patient, uuid.UUID(data["patient_id"]))
        doctor = await db.get(Doctor, uuid.UUID(data["referring_doctor_id"]))
        if not patient or not doctor:
            raise ValueError("Patient or doctor not found")

        patient_name = f"{patient.first_name} {patient.last_name}"

        referral = Referral(
            id=uuid.uuid4(),
            referral_type="external_clinic",
            patient_id=patient.id,
            referring_doctor_id=doctor.id,
            external_entity_name=data["clinic_name"],
            external_entity_email=data["clinic_email"],
            reason=data["reason"],
            data_scope=data.get("data_scope", "summary"),
            status="pending_approval",
        )
        db.add(referral)
        await db.flush()

        try:
            result = await ApprovalGateway.approve_external_referral(
                patient_mrn=patient.mrn,
                patient_name=patient_name,
                clinic_name=data["clinic_name"],
                reason=data["reason"],
                data_scope=referral.data_scope,
            )

            referral.status = "approved"
            referral.approval_job_id = result.get("job_id")
            referral.final_data_scope = referral.data_scope

            # Share via Google Drive Token Vault
            share_result = await NotificationService.share_patient_records(
                patient_name=patient_name,
                patient_mrn=patient.mrn,
                recipient_email=data["clinic_email"],
                data_scope=referral.data_scope,
            )
            if share_result.get("final_params", {}).get("link"):
                referral.shared_drive_link = share_result["final_params"]["link"]

            # Notify clinic via Gmail
            await NotificationService.notify_referral_clinic(
                clinic_email=data["clinic_email"],
                patient_name=patient_name,
                reason=data["reason"],
            )

            referral.audit_notes = (
                f"Shared {referral.data_scope} records with {data['clinic_name']}. "
                f"Approved by Dr. {doctor.first_name} {doctor.last_name}."
            )

            db.add(ActivityLog(
                event_type="referral_approved",
                category="hipaa",
                title=f"Referral: {patient_name} → {data['clinic_name']}",
                description=f"External referral approved. Scope: {referral.data_scope}",
                severity="info",
                entity_type="referral",
                entity_id=str(referral.id),
                approval_job_id=referral.approval_job_id,
                extra_data={
                    "patient_mrn": patient.mrn,
                    "clinic": data["clinic_name"],
                    "data_scope": referral.data_scope,
                },
            ))

        except ApprovalDenied as e:
            referral.status = "denied"
            referral.approval_job_id = e.job_id
            db.add(ActivityLog(
                event_type="referral_denied",
                category="hipaa",
                title=f"Referral Denied: {patient_name}",
                description=f"External referral denied: {e.status}",
                severity="warning",
                entity_type="referral",
                entity_id=str(referral.id),
            ))

        await db.commit()
        await db.refresh(referral)
        return {"referral": referral, "approval_status": referral.status}

    @staticmethod
    async def create_insurance_data_request(db: AsyncSession, data: dict) -> dict:
        """
        Insurance data request → all_of_n with partial_approval.
        Approver can narrow data_scope from 'full' to 'summary'.
        """
        patient = await db.get(Patient, uuid.UUID(data["patient_id"]))
        if not patient:
            raise ValueError("Patient not found")

        insurance = await db.get(InsuranceProvider, uuid.UUID(data["insurance_provider_id"]))
        if not insurance:
            raise ValueError("Insurance provider not found")

        patient_name = f"{patient.first_name} {patient.last_name}"

        req = InsuranceRequest(
            id=uuid.uuid4(),
            patient_id=patient.id,
            insurance_provider_id=insurance.id,
            request_type="data_request",
            requested_data_scope=data.get("requested_data_scope", "summary"),
            reason=data["reason"],
            status="pending_approval",
        )
        db.add(req)
        await db.flush()

        try:
            result = await ApprovalGateway.approve_insurance_data_request(
                patient_mrn=patient.mrn,
                patient_name=patient_name,
                insurance_name=insurance.name,
                requested_data_scope=req.requested_data_scope,
                reason=data["reason"],
            )

            req.status = "approved"
            req.approval_job_id = result.get("job_id")

            # Check for partial approval — approver may have narrowed scope
            final_params = result.get("final_params", {})
            final_scope = final_params.get("requested_data_scope", req.requested_data_scope)
            req.final_data_scope = final_scope

            # Share via Drive with the approved scope
            await NotificationService.share_patient_records(
                patient_name=patient_name,
                patient_mrn=patient.mrn,
                recipient_email=insurance.contact_email,
                data_scope=final_scope,
            )

            partial = final_scope != req.requested_data_scope
            db.add(ActivityLog(
                event_type="insurance_data_shared" if not partial else "insurance_data_partial",
                category="hipaa",
                title=f"Insurance Data: {patient_name} → {insurance.name}",
                description=(
                    f"Data shared with {insurance.name}. "
                    f"Requested: {req.requested_data_scope}, Final: {final_scope}."
                    f"{' Scope narrowed by approver.' if partial else ''}"
                ),
                severity="warning" if partial else "info",
                entity_type="insurance_request",
                entity_id=str(req.id),
                approval_job_id=req.approval_job_id,
                extra_data={
                    "patient_mrn": patient.mrn,
                    "requested_scope": req.requested_data_scope,
                    "final_scope": final_scope,
                    "partial_approval": partial,
                },
            ))

        except ApprovalDenied as e:
            req.status = "denied"
            req.approval_job_id = e.job_id

        await db.commit()
        await db.refresh(req)
        return {
            "request": req,
            "approval_status": req.status,
            "partial_approval": req.final_data_scope != req.requested_data_scope if req.final_data_scope else False,
        }

    @staticmethod
    async def create_research_export(db: AsyncSession, data: dict) -> dict:
        """
        Research data export → sequential: ethics board → CMO → hospital director.
        Amount anomaly: 100+ patients auto-flagged.
        """
        patient_count = data.get("patient_count", len(data.get("patient_ids", [])))
        if patient_count == 0:
            patient_count = len(data.get("patient_ids", []))

        # Use first patient for the referral record, or create a placeholder
        patient_id = data.get("patient_ids", [None])[0] if data.get("patient_ids") else None

        referral = Referral(
            id=uuid.uuid4(),
            referral_type="research_export",
            patient_id=uuid.UUID(patient_id) if patient_id else uuid.uuid4(),
            referring_doctor_id=uuid.UUID(data["referring_doctor_id"]),
            external_entity_name=data["research_entity_name"],
            external_entity_email=data["research_entity_email"],
            reason=data["reason"],
            data_scope=data.get("data_scope", "anonymized"),
            patient_count=patient_count,
            status="pending_approval",
        )
        db.add(referral)
        await db.flush()

        try:
            result = await ApprovalGateway.approve_research_export(
                research_entity=data["research_entity_name"],
                reason=data["reason"],
                patient_count=patient_count,
                data_scope=referral.data_scope,
            )

            referral.status = "approved"
            referral.approval_job_id = result.get("job_id")

            # Share anonymized data
            await NotificationService.share_patient_records(
                patient_name=f"Research_Export_{patient_count}_patients",
                patient_mrn="RESEARCH",
                recipient_email=data["research_entity_email"],
                data_scope="anonymized",
            )

            anomaly = patient_count >= 100
            db.add(ActivityLog(
                event_type="research_export_approved",
                category="hipaa",
                title=f"Research Export: {patient_count} patients → {data['research_entity_name']}",
                description=(
                    f"Research data export approved. {patient_count} patients, {referral.data_scope} data. "
                    f"{'⚠️ Amount anomaly: 100+ patients flagged.' if anomaly else ''}"
                ),
                severity="warning" if anomaly else "info",
                entity_type="referral",
                entity_id=str(referral.id),
                approval_job_id=referral.approval_job_id,
                extra_data={"patient_count": patient_count, "amount_anomaly": anomaly},
            ))

        except ApprovalDenied as e:
            referral.status = "denied"
            referral.approval_job_id = e.job_id

        await db.commit()
        await db.refresh(referral)
        return {"referral": referral, "approval_status": referral.status}

    @staticmethod
    async def get_referrals(db: AsyncSession, referral_type: str | None = None, limit: int = 50):
        query = select(Referral).order_by(Referral.created_at.desc()).limit(limit)
        if referral_type:
            query = query.where(Referral.referral_type == referral_type)
        result = await db.execute(query)
        return result.scalars().all()
