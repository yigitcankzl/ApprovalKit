"""
Prescription Service — Handles all prescription workflows with ApprovalKit.

Approval flows:
  - Routine medication:   specific (doctor only)
  - Controlled substance: sequential (doctor → pharmacist)
  - Dose change:         all_of_n (doctor + pharmacist + CMO)
"""
import uuid
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.models.prescription import Prescription, DoseChange
from backend.models.patient import Patient
from backend.models.doctor import Doctor
from backend.models.activity import ActivityLog
from backend.services.approval_gateway import ApprovalGateway, ApprovalDenied
from backend.services.notification_service import NotificationService

logger = logging.getLogger("healthcare.prescriptions")


def _rx_number(count: int) -> str:
    return f"RX-{count + 1:07d}"


class PrescriptionService:

    @staticmethod
    async def create_prescription_record(db: AsyncSession, data: dict) -> dict:
        """Create prescription DB record only (no approval). Returns immediately."""
        patient = await db.get(Patient, uuid.UUID(data["patient_id"]))
        doctor = await db.get(Doctor, uuid.UUID(data["prescribing_doctor_id"]))
        if not patient or not doctor:
            raise ValueError("Patient or doctor not found")

        count = await db.scalar(select(func.count()).select_from(Prescription))
        rx_number = _rx_number(count or 0)

        rx = Prescription(
            id=uuid.uuid4(),
            rx_number=rx_number,
            patient_id=patient.id,
            prescribing_doctor_id=doctor.id,
            medication_name=data["medication_name"],
            medication_code=data.get("medication_code", ""),
            dosage=data["dosage"],
            frequency=data.get("frequency", "once daily"),
            quantity=data.get("quantity", 30),
            refills=data.get("refills", 0),
            is_controlled=data.get("is_controlled", False),
            schedule_class=data.get("schedule_class"),
            pharmacy_email=data.get("pharmacy_email", "pharmacy@medcore-hospital.com"),
            notes=data.get("notes"),
            status="pending_approval",
        )
        db.add(rx)
        await db.commit()
        return {"prescription": rx, "approval_status": "pending_approval"}

    @staticmethod
    async def create_prescription(db: AsyncSession, data: dict, rx_id: str | None = None) -> dict:
        """
        Run approval flow for a prescription. Called from background task.
        """
        if rx_id:
            rx = await db.get(Prescription, uuid.UUID(rx_id))
            if not rx:
                raise ValueError("Prescription not found")
            patient = await db.get(Patient, rx.patient_id)
            doctor = await db.get(Doctor, rx.prescribing_doctor_id)
        else:
            patient = await db.get(Patient, uuid.UUID(data["patient_id"]))
            doctor = await db.get(Doctor, uuid.UUID(data["prescribing_doctor_id"]))
            if not patient or not doctor:
                raise ValueError("Patient or doctor not found")

            count = await db.scalar(select(func.count()).select_from(Prescription))
            rx_number = _rx_number(count or 0)

            rx = Prescription(
                id=uuid.uuid4(),
                rx_number=rx_number,
                patient_id=patient.id,
                prescribing_doctor_id=doctor.id,
                medication_name=data["medication_name"],
                medication_code=data.get("medication_code", ""),
                dosage=data["dosage"],
                frequency=data.get("frequency", "once daily"),
                quantity=data.get("quantity", 30),
                refills=data.get("refills", 0),
                is_controlled=data.get("is_controlled", False),
                schedule_class=data.get("schedule_class"),
                pharmacy_email=data.get("pharmacy_email", "pharmacy@medcore-hospital.com"),
                notes=data.get("notes"),
                status="pending_approval",
            )
            db.add(rx)
            await db.flush()

        patient_name = f"{patient.first_name} {patient.last_name}"
        doctor_name = f"{doctor.first_name} {doctor.last_name}"

        # Route through ApprovalKit
        try:
            if rx.is_controlled:
                # Sequential: doctor → pharmacist
                result = await ApprovalGateway.approve_controlled_substance(
                    medication_name=rx.medication_name,
                    dosage=rx.dosage,
                    schedule_class=rx.schedule_class or "II",
                    patient_mrn=patient.mrn,
                    patient_name=patient_name,
                    doctor_name=doctor_name,
                )
                rx.approved_by_doctor = True
                rx.approved_by_pharmacist = True
            else:
                # Specific: doctor only
                result = await ApprovalGateway.approve_routine_prescription(
                    medication_name=rx.medication_name,
                    dosage=rx.dosage,
                    patient_mrn=patient.mrn,
                    patient_name=patient_name,
                    doctor_name=doctor_name,
                )
                rx.approved_by_doctor = True

            rx.status = "approved"
            rx.approval_job_id = result.get("job_id")

            # Notify pharmacy via Gmail Token Vault
            await NotificationService.notify_pharmacy(
                pharmacy_email=rx.pharmacy_email,
                patient_name=patient_name,
                patient_mrn=patient.mrn,
                medication=rx.medication_name,
                dosage=rx.dosage,
                quantity=rx.quantity,
                doctor_name=doctor_name,
            )

            db.add(ActivityLog(
                event_type="prescription_approved",
                category="prescription",
                title=f"Rx Approved: {rx.medication_name} for {patient_name}",
                description=(
                    f"{'Controlled' if rx.is_controlled else 'Routine'} prescription {rx_number} "
                    f"for {rx.medication_name} {rx.dosage} approved."
                ),
                severity="info",
                entity_type="prescription",
                entity_id=str(rx.id),
                approval_job_id=rx.approval_job_id,
                extra_data={
                    "medication": rx.medication_name,
                    "controlled": rx.is_controlled,
                    "patient_mrn": patient.mrn,
                },
            ))

        except ApprovalDenied as e:
            rx.status = "denied"
            rx.approval_job_id = e.job_id
            db.add(ActivityLog(
                event_type="prescription_denied",
                category="prescription",
                title=f"Rx Denied: {rx.medication_name} for {patient_name}",
                description=f"Prescription {rx_number} denied: {e.status}",
                severity="warning",
                entity_type="prescription",
                entity_id=str(rx.id),
                approval_job_id=e.job_id,
            ))

        await db.commit()
        await db.refresh(rx)
        return {"prescription": rx, "approval_status": rx.status}

    @staticmethod
    async def request_dose_change(db: AsyncSession, data: dict) -> dict:
        """
        Request dose change — all_of_n: doctor + pharmacist + CMO.
        First dose change triggers scope creep detection in ApprovalKit.
        """
        rx = await db.get(Prescription, uuid.UUID(data["prescription_id"]))
        if not rx:
            raise ValueError("Prescription not found")

        patient = await db.get(Patient, rx.patient_id)
        doctor = await db.get(Doctor, uuid.UUID(data["requested_by_doctor_id"]))
        if not patient or not doctor:
            raise ValueError("Patient or doctor not found")

        # Check if this is the first dose change for this prescription
        existing = await db.scalar(
            select(func.count()).select_from(DoseChange).where(
                DoseChange.prescription_id == rx.id
            )
        )
        is_first = (existing or 0) == 0

        dc = DoseChange(
            id=uuid.uuid4(),
            prescription_id=rx.id,
            patient_id=patient.id,
            requested_by_doctor_id=doctor.id,
            previous_dosage=rx.dosage,
            new_dosage=data["new_dosage"],
            reason=data["reason"],
            is_first_change=is_first,
            status="pending_approval",
        )
        db.add(dc)
        await db.flush()

        patient_name = f"{patient.first_name} {patient.last_name}"
        doctor_name = f"{doctor.first_name} {doctor.last_name}"

        try:
            result = await ApprovalGateway.approve_dose_change(
                medication_name=rx.medication_name,
                previous_dosage=rx.dosage,
                new_dosage=data["new_dosage"],
                patient_mrn=patient.mrn,
                patient_name=patient_name,
                doctor_name=doctor_name,
                is_first_change=is_first,
            )

            dc.status = "approved"
            dc.approval_job_id = result.get("job_id")
            rx.dosage = data["new_dosage"]
            rx.updated_at = datetime.utcnow()

            # Notify patient and pharmacy
            await NotificationService.notify_patient_dose_change(
                patient_email=patient.email,
                patient_name=patient_name,
                medication=rx.medication_name,
                old_dose=dc.previous_dosage,
                new_dose=dc.new_dosage,
            )
            await NotificationService.notify_pharmacy(
                pharmacy_email=rx.pharmacy_email,
                patient_name=patient_name,
                patient_mrn=patient.mrn,
                medication=rx.medication_name,
                dosage=dc.new_dosage,
                quantity=rx.quantity,
                doctor_name=doctor_name,
            )

            severity = "warning" if is_first else "info"
            db.add(ActivityLog(
                event_type="dose_change_approved",
                category="prescription",
                title=f"Dose Change: {rx.medication_name} {dc.previous_dosage} → {dc.new_dosage}",
                description=(
                    f"Dose change approved for {patient_name}. "
                    f"{'⚠️ First dose change — scope creep flagged.' if is_first else ''}"
                ),
                severity=severity,
                entity_type="dose_change",
                entity_id=str(dc.id),
                approval_job_id=dc.approval_job_id,
                extra_data={"is_first_change": is_first, "patient_mrn": patient.mrn},
            ))

        except ApprovalDenied as e:
            dc.status = "denied"
            dc.approval_job_id = e.job_id
            db.add(ActivityLog(
                event_type="dose_change_denied",
                category="prescription",
                title=f"Dose Change Denied: {rx.medication_name}",
                description=f"Dose change denied: {e.status}",
                severity="warning",
                entity_type="dose_change",
                entity_id=str(dc.id),
            ))

        await db.commit()
        await db.refresh(dc)
        return {"dose_change": dc, "approval_status": dc.status}

    @staticmethod
    async def get_prescriptions(db: AsyncSession, patient_id: str | None = None, limit: int = 50, offset: int = 0):
        query = select(Prescription).order_by(Prescription.created_at.desc()).limit(limit).offset(offset)
        if patient_id:
            query = query.where(Prescription.patient_id == uuid.UUID(patient_id))
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_prescription(db: AsyncSession, prescription_id: str):
        return await db.get(Prescription, uuid.UUID(prescription_id))
