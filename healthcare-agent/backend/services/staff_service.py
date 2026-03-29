"""
Staff Service — Delegation, access management, shift operations.

Approval flows:
  Basic access:        specific (IT admin)
  Patient records:     step-up → all_of_n (IT + CMO)
  Medication system:   all_of_n (IT + pharmacy lead + CMO)
  Delegation:          Updates ApprovalKit approver delegation fields
"""
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.doctor import Doctor
from backend.models.staff import Staff
from backend.models.access_request import AccessRequest
from backend.models.shift import ShiftSchedule
from backend.models.activity import ActivityLog
from backend.services.approval_gateway import ApprovalGateway, ApprovalDenied
from backend.services.notification_service import NotificationService

logger = logging.getLogger("healthcare.staff")


class StaffService:

    @staticmethod
    async def request_access_change(db: AsyncSession, data: dict) -> dict:
        """
        Request access level change.
        Approval model depends on requested level:
          basic:            specific (IT admin)
          patient_records:  step-up → CMO
          medication_system: all_of_n (IT + pharmacy lead + CMO)
        """
        staff = await db.get(Staff, uuid.UUID(data["staff_id"]))
        if not staff:
            raise ValueError("Staff member not found")

        req = AccessRequest(
            id=uuid.uuid4(),
            staff_id=staff.id,
            requested_access_level=data["requested_access_level"],
            current_access_level=staff.access_level,
            reason=data["reason"],
            status="pending_approval",
        )
        db.add(req)
        await db.flush()

        staff_name = f"{staff.first_name} {staff.last_name}"

        try:
            result = await ApprovalGateway.approve_access_change(
                employee_name=staff_name,
                employee_id=staff.employee_id,
                current_level=staff.access_level,
                requested_level=data["requested_access_level"],
                reason=data["reason"],
            )

            req.status = "approved"
            req.approval_job_id = result.get("job_id")
            staff.access_level = data["requested_access_level"]

            await NotificationService.send_email(
                recipient=staff.email,
                subject="Access Level Updated",
                body=(
                    f"Dear {staff_name},\n\n"
                    f"Your access level has been updated to: {data['requested_access_level']}\n"
                    f"Previous level: {req.current_access_level}\n\n"
                    f"— MedCore IT Department"
                ),
                email_type="access_update",
            )

            db.add(ActivityLog(
                event_type="access_changed",
                category="staff",
                title=f"Access: {staff_name} → {data['requested_access_level']}",
                description=(
                    f"Access level changed from {req.current_access_level} "
                    f"to {data['requested_access_level']}"
                ),
                severity="warning" if data["requested_access_level"] in ("medication_system", "full") else "info",
                entity_type="access_request",
                entity_id=str(req.id),
                approval_job_id=req.approval_job_id,
                extra_data={"employee_id": staff.employee_id},
            ))

        except ApprovalDenied as e:
            req.status = "denied"
            req.approval_job_id = e.job_id
            db.add(ActivityLog(
                event_type="access_denied",
                category="staff",
                title=f"Access Denied: {staff_name}",
                description=f"Access change to {data['requested_access_level']} denied: {e.status}",
                severity="warning",
                entity_type="access_request",
                entity_id=str(req.id),
            ))

        await db.commit()
        await db.refresh(req)
        return {"request": req, "approval_status": req.status}

    @staticmethod
    async def set_delegation(db: AsyncSession, doctor_id: str, data: dict) -> dict:
        """
        Set vacation delegation for a doctor.
        Updates local DB + notifies patients via Gmail + updates calendar.
        """
        doctor = await db.get(Doctor, uuid.UUID(doctor_id))
        delegate = await db.get(Doctor, uuid.UUID(data["delegate_to_id"]))
        if not doctor or not delegate:
            raise ValueError("Doctor or delegate not found")

        days = data.get("days", 14)
        doctor.on_vacation = True
        doctor.delegate_to_id = delegate.id
        doctor.delegate_until = datetime.utcnow() + timedelta(days=days)

        doctor_name = f"{doctor.first_name} {doctor.last_name}"
        delegate_name = f"{delegate.first_name} {delegate.last_name}"

        start_date = datetime.utcnow().strftime("%Y-%m-%d")
        end_date = doctor.delegate_until.strftime("%Y-%m-%d")

        # Notify via Slack
        await NotificationService.send_slack_message(
            channel="#medical",
            message=(
                f"📋 *Delegation Notice*\n"
                f"Dr. {doctor_name} is on leave until {end_date}.\n"
                f"Dr. {delegate_name} is covering all duties."
            ),
        )

        # Delegate shifts
        shifts = await db.execute(
            select(ShiftSchedule)
            .where(ShiftSchedule.doctor_id == doctor.id)
            .where(ShiftSchedule.shift_date >= datetime.utcnow().date())
            .where(ShiftSchedule.shift_date <= doctor.delegate_until.date())
        )
        for shift in shifts.scalars():
            shift.status = "delegated"
            shift.delegated_to_id = delegate.id

        db.add(ActivityLog(
            event_type="delegation_set",
            category="staff",
            title=f"Delegation: Dr. {doctor_name} → Dr. {delegate_name}",
            description=f"Dr. {doctor_name} on leave until {end_date}. Delegated to Dr. {delegate_name}.",
            severity="info",
            entity_type="doctor",
            entity_id=str(doctor.id),
            extra_data={
                "delegate_id": str(delegate.id),
                "until": end_date,
            },
        ))

        await db.commit()
        await db.refresh(doctor)
        return {
            "doctor": doctor,
            "delegate": delegate,
            "delegation_until": end_date,
        }

    @staticmethod
    async def clear_delegation(db: AsyncSession, doctor_id: str) -> dict:
        doctor = await db.get(Doctor, uuid.UUID(doctor_id))
        if not doctor:
            raise ValueError("Doctor not found")

        doctor.on_vacation = False
        doctor.delegate_to_id = None
        doctor.delegate_until = None

        # Restore shifts
        shifts = await db.execute(
            select(ShiftSchedule)
            .where(ShiftSchedule.doctor_id == doctor.id)
            .where(ShiftSchedule.status == "delegated")
        )
        for shift in shifts.scalars():
            shift.status = "scheduled"
            shift.delegated_to_id = None

        await db.commit()
        await db.refresh(doctor)
        return {"doctor": doctor}

    @staticmethod
    async def get_doctors(db: AsyncSession, specialty: str | None = None):
        query = select(Doctor).order_by(Doctor.last_name)
        if specialty:
            query = query.where(Doctor.specialty == specialty)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_staff(db: AsyncSession, role: str | None = None):
        query = select(Staff).order_by(Staff.last_name)
        if role:
            query = query.where(Staff.role == role)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_shifts(db: AsyncSession, doctor_id: str | None = None, limit: int = 60):
        query = select(ShiftSchedule).order_by(ShiftSchedule.shift_date.desc()).limit(limit)
        if doctor_id:
            query = query.where(ShiftSchedule.doctor_id == uuid.UUID(doctor_id))
        result = await db.execute(query)
        return result.scalars().all()
