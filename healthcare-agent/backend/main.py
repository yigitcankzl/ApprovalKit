"""
Healthcare AI Agent — FastAPI Application
==========================================
A comprehensive healthcare management system powered by ApprovalKit
for HIPAA-compliant human-in-the-loop approval workflows.
"""
import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, time
from decimal import Decimal

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from backend.config import settings
from backend.database import engine, Base, get_db, async_session
from backend.models import *
from backend.seed.generate import generate_all

from backend.routes.patients import router as patients_router
from backend.routes.prescriptions import router as prescriptions_router
from backend.routes.billing import router as billing_router
from backend.routes.referrals import router as referrals_router
from backend.routes.emergency import router as emergency_router
from backend.routes.staff import router as staff_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.scenarios import router as scenarios_router
from backend.routes.chat import router as chat_router
from a2a.server import router as a2a_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("healthcare")


async def _bootstrap_with_approvalkit():
    """Register this agent + connections + approvers + rules in ApprovalKit on startup."""
    import httpx
    import yaml
    import os

    url = settings.APPROVALKIT_URL.rstrip("/")
    if not url or not settings.APPROVALKIT_API_KEY:
        logger.warning("ApprovalKit not configured — skipping bootstrap")
        return

    yaml_path = os.path.join(os.path.dirname(__file__), "..", "setup", "rules.yaml")
    if not os.path.exists(yaml_path):
        logger.warning("rules.yaml not found — skipping bootstrap")
        return

    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    payload = {
        "agent": {
            "name": config["agent"]["name"],
            "description": config["agent"].get("description", ""),
            "icon": config["agent"].get("icon", "bot"),
            "scenarios": config["agent"].get("scenarios", []),
        },
        "connections": [
            {"slug": c["slug"], "name": c["name"], "service": c["service"],
             "actions": [a["action"] for a in c["actions"]]}
            for c in config.get("connections", [])
        ],
        "approvers": config.get("approvers", []),
        "rules": config.get("rules", []),
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{url}/api/v1/agents/bootstrap",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if r.status_code in (200, 201):
                data = r.json()
                created = data.get("created", {})
                logger.info(
                    f"ApprovalKit bootstrap: agent={created.get('agent', 'exists')}, "
                    f"connections={created.get('connections', 0)}, "
                    f"approvers={created.get('approvers', 0)}, "
                    f"rules={created.get('rules', 0)}, "
                    f"scenarios={created.get('scenarios', 0)}"
                )
            else:
                logger.warning(f"ApprovalKit bootstrap failed: {r.status_code} {r.text[:200]}")
    except Exception as e:
        logger.warning(f"ApprovalKit bootstrap error (will retry on next startup): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    # Auto-register with ApprovalKit
    await _bootstrap_with_approvalkit()

    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Healthcare AI Agent",
    description="HIPAA-compliant healthcare management powered by ApprovalKit",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3003", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Signature"],
)

# Register routers
app.include_router(patients_router)
app.include_router(prescriptions_router)
app.include_router(billing_router)
app.include_router(referrals_router)
app.include_router(emergency_router)
app.include_router(staff_router)
app.include_router(dashboard_router)
app.include_router(scenarios_router)
app.include_router(chat_router)
app.include_router(a2a_router)


@app.get("/")
async def root():
    return {
        "name": "Healthcare AI Agent",
        "version": "1.0.0",
        "hospital": settings.HOSPITAL_NAME,
        "approvalkit_url": settings.APPROVALKIT_URL,
        "status": "running",
    }


@app.get("/api/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "database": db_status,
        "approvalkit": settings.APPROVALKIT_URL,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/seed")
async def seed_database():
    """Populate database with realistic demo data."""
    async with async_session() as db:
        # Check if already seeded
        count = await db.scalar(select(func.count()).select_from(Patient))
        if count and count > 0:
            return {"status": "already_seeded", "patients": count}

        data = generate_all()

        # Insurance providers
        for p in data["insurance_providers"]:
            db.add(InsuranceProvider(
                id=uuid.UUID(p["id"]),
                name=p["name"], plan_type=p["plan_type"],
                contact_email=p["contact_email"], phone=p["phone"],
                coverage_details=p["coverage_details"],
            ))
        await db.flush()

        # Doctors
        for d in data["doctors"]:
            db.add(Doctor(
                id=uuid.UUID(d["id"]),
                npi=d["npi"], first_name=d["first_name"], last_name=d["last_name"],
                email=d["email"], phone=d["phone"],
                specialty=d["specialty"], department=d["department"],
                license_number=d["license_number"],
                is_cmo=d["is_cmo"], is_active=d["is_active"],
                on_vacation=d["on_vacation"],
                delegate_to_id=uuid.UUID(d["delegate_to_id"]) if d["delegate_to_id"] else None,
                delegate_until=datetime.fromisoformat(d["delegate_until"]) if d["delegate_until"] else None,
            ))
        await db.flush()

        # Staff
        for s in data["staff"]:
            db.add(Staff(
                id=uuid.UUID(s["id"]),
                employee_id=s["employee_id"],
                first_name=s["first_name"], last_name=s["last_name"],
                email=s["email"], phone=s["phone"],
                role=s["role"], department=s["department"],
                access_level=s["access_level"], is_active=s["is_active"],
            ))
        await db.flush()

        # Patients
        for p in data["patients"]:
            db.add(Patient(
                id=uuid.UUID(p["id"]),
                mrn=p["mrn"], first_name=p["first_name"], last_name=p["last_name"],
                date_of_birth=date.fromisoformat(p["date_of_birth"]),
                gender=p["gender"], ssn_masked=p["ssn_masked"],
                phone=p["phone"], email=p["email"],
                address=p["address"], emergency_contact=p["emergency_contact"],
                blood_type=p["blood_type"], allergies=p["allergies"],
                conditions=p["conditions"], medications_current=p["medications_current"],
                primary_doctor_id=uuid.UUID(p["primary_doctor_id"]) if p["primary_doctor_id"] else None,
                insurance_id=uuid.UUID(p["insurance_id"]) if p["insurance_id"] else None,
                insurance_policy_number=p["insurance_policy_number"],
                status=p["status"],
                admitted_at=datetime.fromisoformat(p["admitted_at"]) if p["admitted_at"] else None,
            ))
        await db.flush()

        # Appointments
        for a in data["appointments"]:
            db.add(Appointment(
                id=uuid.UUID(a["id"]),
                patient_id=uuid.UUID(a["patient_id"]),
                doctor_id=uuid.UUID(a["doctor_id"]),
                appointment_type=a["appointment_type"],
                scheduled_at=datetime.fromisoformat(a["scheduled_at"]),
                duration_minutes=a["duration_minutes"],
                location=a["location"],
                status=a["status"],
            ))

        # Billing records
        for b in data["billing_records"]:
            db.add(BillingRecord(
                id=uuid.UUID(b["id"]),
                invoice_number=b["invoice_number"],
                patient_id=uuid.UUID(b["patient_id"]),
                description=b["description"],
                procedure_code=b["procedure_code"],
                amount=Decimal(b["amount"]),
                insurance_covered=Decimal(b["insurance_covered"]),
                patient_responsibility=Decimal(b["patient_responsibility"]),
                status=b["status"],
            ))

        # Shifts
        for s in data["shifts"]:
            db.add(ShiftSchedule(
                id=uuid.UUID(s["id"]),
                doctor_id=uuid.UUID(s["doctor_id"]),
                shift_date=date.fromisoformat(s["shift_date"]),
                start_time=time.fromisoformat(s["start_time"]),
                end_time=time.fromisoformat(s["end_time"]),
                department=s["department"],
                status=s["status"],
            ))

        # Prescriptions
        for rx in data["prescriptions"]:
            db.add(Prescription(
                id=uuid.UUID(rx["id"]),
                rx_number=rx["rx_number"],
                patient_id=uuid.UUID(rx["patient_id"]),
                prescribing_doctor_id=uuid.UUID(rx["prescribing_doctor_id"]),
                medication_name=rx["medication_name"],
                medication_code=rx["medication_code"],
                dosage=rx["dosage"],
                frequency=rx["frequency"],
                quantity=rx["quantity"],
                refills=rx["refills"],
                is_controlled=rx["is_controlled"],
                schedule_class=rx["schedule_class"],
                status=rx["status"],
                approved_by_doctor=rx["approved_by_doctor"],
                approved_by_pharmacist=rx["approved_by_pharmacist"],
                approved_by_cmo=rx["approved_by_cmo"],
                pharmacy_email=rx["pharmacy_email"],
            ))

        # Activity log for seeding
        db.add(ActivityLog(
            event_type="system_seeded",
            category="system",
            title="Database Seeded",
            description=(
                f"Generated {len(data['patients'])} patients, {len(data['doctors'])} doctors, "
                f"{len(data['staff'])} staff, {len(data['prescriptions'])} prescriptions, "
                f"{len(data['billing_records'])} billing records"
            ),
            severity="info",
        ))

        await db.commit()

        return {
            "status": "seeded",
            "counts": {
                "insurance_providers": len(data["insurance_providers"]),
                "doctors": len(data["doctors"]),
                "staff": len(data["staff"]),
                "patients": len(data["patients"]),
                "appointments": len(data["appointments"]),
                "billing_records": len(data["billing_records"]),
                "shifts": len(data["shifts"]),
                "prescriptions": len(data["prescriptions"]),
            },
        }


# Required import for seed endpoint
from sqlalchemy import func
