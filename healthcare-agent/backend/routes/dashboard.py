"""
Dashboard & Real-Time Activity Feed
SSE endpoint for live updates + aggregated stats.
"""
import asyncio
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.database import get_db
from backend.models.patient import Patient
from backend.models.prescription import Prescription
from backend.models.billing import BillingRecord
from backend.models.emergency import EmergencyEvent
from backend.models.appointment import Appointment
from backend.models.activity import ActivityLog

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    total_patients = await db.scalar(select(func.count()).select_from(Patient)) or 0
    active_patients = await db.scalar(
        select(func.count()).select_from(Patient).where(Patient.status == "active")
    ) or 0

    pending_prescriptions = await db.scalar(
        select(func.count()).select_from(Prescription).where(Prescription.status == "pending_approval")
    ) or 0

    active_emergencies = await db.scalar(
        select(func.count()).select_from(EmergencyEvent)
        .where(EmergencyEvent.status.in_(["active", "investigating", "escalated"]))
    ) or 0

    today = datetime.utcnow().date()
    todays_appointments = await db.scalar(
        select(func.count()).select_from(Appointment)
        .where(func.date(Appointment.scheduled_at) == today)
        .where(Appointment.status == "scheduled")
    ) or 0

    total_billed = await db.scalar(select(func.sum(BillingRecord.amount))) or 0
    pending_billing = await db.scalar(
        select(func.sum(BillingRecord.amount)).where(BillingRecord.status == "pending")
    ) or 0

    approved_rx = await db.scalar(
        select(func.count()).select_from(Prescription).where(Prescription.status == "approved")
    ) or 0
    denied_rx = await db.scalar(
        select(func.count()).select_from(Prescription).where(Prescription.status == "denied")
    ) or 0

    recent_activity = await db.scalar(
        select(func.count()).select_from(ActivityLog)
        .where(ActivityLog.created_at >= datetime.utcnow() - timedelta(hours=24))
    ) or 0

    return {
        "patients": {
            "total": total_patients,
            "active": active_patients,
        },
        "prescriptions": {
            "pending_approval": pending_prescriptions,
            "approved": approved_rx,
            "denied": denied_rx,
        },
        "emergencies": {
            "active": active_emergencies,
        },
        "appointments": {
            "today": todays_appointments,
        },
        "billing": {
            "total_billed": float(total_billed),
            "pending": float(pending_billing),
        },
        "activity": {
            "last_24h": recent_activity,
        },
    }


@router.get("/activity")
async def activity_feed(limit: int = 50, category: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    if category:
        query = query.where(ActivityLog.category == category)
    result = await db.execute(query)
    activities = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "event_type": a.event_type,
            "category": a.category,
            "title": a.title,
            "description": a.description,
            "severity": a.severity,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "approval_job_id": a.approval_job_id,
            "metadata": a.extra_data,
            "created_at": a.created_at.isoformat(),
        }
        for a in activities
    ]


@router.get("/activity/stream")
async def activity_stream(db: AsyncSession = Depends(get_db)):
    """Server-Sent Events stream for real-time activity updates."""
    async def event_generator():
        last_id = None
        while True:
            async with async_session() as session:
                query = select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(5)
                if last_id:
                    query = query.where(ActivityLog.id != last_id)
                result = await session.execute(query)
                activities = result.scalars().all()

                for a in activities:
                    if last_id and str(a.id) == last_id:
                        continue
                    event_data = json.dumps({
                        "id": str(a.id),
                        "event_type": a.event_type,
                        "category": a.category,
                        "title": a.title,
                        "severity": a.severity,
                        "created_at": a.created_at.isoformat(),
                    })
                    yield f"data: {event_data}\n\n"
                    last_id = str(a.id)

            await asyncio.sleep(3)

    from backend.database import async_session
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/approval-status")
async def approval_status(db: AsyncSession = Depends(get_db)):
    """List all pending approval items across all domains."""
    pending_rx = await db.execute(
        select(Prescription).where(Prescription.status == "pending_approval").limit(20)
    )
    pending_billing = await db.execute(
        select(BillingRecord).where(BillingRecord.status == "pending").limit(20)
    )

    items = []
    for rx in pending_rx.scalars():
        items.append({
            "type": "prescription",
            "id": str(rx.id),
            "description": f"{rx.medication_name} {rx.dosage}",
            "patient": f"{rx.patient.first_name} {rx.patient.last_name}" if rx.patient else "Unknown",
            "approval_job_id": rx.approval_job_id,
            "created_at": rx.created_at.isoformat(),
        })

    for bill in pending_billing.scalars():
        items.append({
            "type": "billing",
            "id": str(bill.id),
            "description": f"{bill.description} — ${bill.amount:,.2f}",
            "patient": f"{bill.patient.first_name} {bill.patient.last_name}" if bill.patient else "Unknown",
            "approval_job_id": bill.approval_job_id,
            "created_at": bill.created_at.isoformat(),
        })

    return sorted(items, key=lambda x: x["created_at"], reverse=True)
