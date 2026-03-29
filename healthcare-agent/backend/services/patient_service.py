"""
Patient Service — Registration, onboarding, and management.
"""
import uuid
import logging
from datetime import date, datetime
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.models.patient import Patient
from backend.models.doctor import Doctor
from backend.models.activity import ActivityLog
from backend.services.notification_service import NotificationService

logger = logging.getLogger("healthcare.patients")


class PatientService:

    @staticmethod
    async def register_patient(db: AsyncSession, data: dict) -> dict:
        """
        Full patient onboarding flow:
        1. Create patient record
        2. Email assigned doctor (Gmail Token Vault)
        3. Slack #intake announcement
        4. Start insurance verification
        5. Schedule first appointment (Google Calendar Token Vault)
        """
        # Generate MRN
        count = await db.scalar(select(func.count()).select_from(Patient))
        mrn = f"MRN-{(count or 0) + 1:05d}"

        patient = Patient(
            id=uuid.uuid4(),
            mrn=mrn,
            first_name=data["first_name"],
            last_name=data["last_name"],
            date_of_birth=date.fromisoformat(data["date_of_birth"]) if isinstance(data["date_of_birth"], str) else data["date_of_birth"],
            gender=data["gender"],
            ssn_masked=f"***-**-{str(uuid.uuid4().int)[:4]}",
            phone=data["phone"],
            email=data["email"],
            address=data.get("address", {}),
            emergency_contact=data.get("emergency_contact", {}),
            blood_type=data.get("blood_type", "O+"),
            allergies=data.get("allergies", []),
            conditions=data.get("conditions", []),
            medications_current=[],
            primary_doctor_id=uuid.UUID(data["primary_doctor_id"]) if data.get("primary_doctor_id") else None,
            insurance_id=uuid.UUID(data["insurance_id"]) if data.get("insurance_id") else None,
            insurance_policy_number=data.get("insurance_policy_number"),
            status="active",
            notes=data.get("notes"),
        )

        db.add(patient)
        await db.flush()

        patient_name = f"{patient.first_name} {patient.last_name}"
        steps_completed = []
        steps_failed = []

        # Step 1: Patient record created
        steps_completed.append("patient_record_created")

        # Step 2: Notify assigned doctor
        if patient.primary_doctor_id:
            doctor = await db.get(Doctor, patient.primary_doctor_id)
            if doctor:
                doctor_name = f"{doctor.first_name} {doctor.last_name}"
                result = await NotificationService.notify_doctor_new_patient(
                    doctor_email=doctor.email,
                    doctor_name=doctor_name,
                    patient_name=patient_name,
                    patient_mrn=mrn,
                )
                if result.get("status") != "notification_denied":
                    steps_completed.append("doctor_notified")
                else:
                    steps_failed.append("doctor_notification")

                # Step 3: Slack intake announcement
                result = await NotificationService.announce_intake(
                    patient_name=patient_name,
                    patient_mrn=mrn,
                    doctor_name=doctor_name,
                    conditions=patient.conditions,
                )
                if result.get("status") != "notification_denied":
                    steps_completed.append("slack_intake_announced")
                else:
                    steps_failed.append("slack_announcement")

                # Step 4: Insurance verification (simulated — internal)
                if patient.insurance_id:
                    steps_completed.append("insurance_verification_started")

                # Step 5: Schedule first appointment
                tomorrow = datetime.utcnow() + timedelta(days=3)
                start = tomorrow.replace(hour=10, minute=0, second=0)
                end = start + timedelta(minutes=30)
                result = await NotificationService.schedule_first_appointment(
                    patient_name=patient_name,
                    doctor_name=doctor_name,
                    doctor_email=doctor.email,
                    patient_email=patient.email,
                    start_time=start.isoformat(),
                    end_time=end.isoformat(),
                )
                if result.get("status") != "notification_denied":
                    steps_completed.append("first_appointment_scheduled")
                else:
                    steps_failed.append("appointment_scheduling")

        # Log activity
        db.add(ActivityLog(
            event_type="patient_registered",
            category="patient",
            title=f"New Patient: {patient_name}",
            description=f"Patient {patient_name} ({mrn}) registered and onboarded. Steps: {', '.join(steps_completed)}",
            severity="info",
            entity_type="patient",
            entity_id=str(patient.id),
            extra_data={"steps_completed": steps_completed, "steps_failed": steps_failed},
        ))

        await db.commit()
        await db.refresh(patient)

        return {
            "patient": patient,
            "mrn": mrn,
            "onboarding": {
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "total_steps": 5,
            },
        }

    @staticmethod
    async def get_patients(db: AsyncSession, status: str | None = None, limit: int = 50, offset: int = 0):
        query = select(Patient).order_by(Patient.created_at.desc()).limit(limit).offset(offset)
        if status:
            query = query.where(Patient.status == status)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_patient(db: AsyncSession, patient_id: str):
        return await db.get(Patient, uuid.UUID(patient_id))

    @staticmethod
    async def get_patient_by_mrn(db: AsyncSession, mrn: str):
        result = await db.execute(select(Patient).where(Patient.mrn == mrn))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_patient(db: AsyncSession, patient_id: str, data: dict):
        patient = await db.get(Patient, uuid.UUID(patient_id))
        if not patient:
            return None
        for key, value in data.items():
            if value is not None and hasattr(patient, key):
                setattr(patient, key, value)
        patient.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(patient)
        return patient

    @staticmethod
    async def get_patient_count(db: AsyncSession):
        return await db.scalar(select(func.count()).select_from(Patient))
