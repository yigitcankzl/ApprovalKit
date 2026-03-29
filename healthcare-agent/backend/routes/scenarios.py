"""
Scenario Runner — Pre-built demo scenarios showcasing all ApprovalKit features.
Each scenario demonstrates a different approval workflow.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db, async_session
from backend.models.patient import Patient
from backend.models.doctor import Doctor
from backend.models.staff import Staff
from backend.models.insurance import InsuranceProvider
from backend.models.activity import ActivityLog
from backend.services.patient_service import PatientService
from backend.services.prescription_service import PrescriptionService
from backend.services.billing_service import BillingService
from backend.services.referral_service import ReferralService
from backend.services.emergency_service import EmergencyService
from backend.services.staff_service import StaffService

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

SCENARIOS = [
    {
        "id": "patient-onboarding",
        "title": "Patient Onboarding",
        "description": "Register Maria Garcia with Type 2 Diabetes, assign to Dr. Smith, trigger full onboarding flow",
        "category": "patient",
        "approval_types": ["auto (notifications via Token Vault)"],
        "steps": [
            "Create patient record",
            "Email Dr. Smith via Gmail (Token Vault)",
            "Slack #intake announcement",
            "Start insurance verification",
            "Schedule first appointment (Google Calendar Token Vault)",
        ],
    },
    {
        "id": "routine-prescription",
        "title": "Routine Prescription",
        "description": "Prescribe Metformin 500mg for Maria Garcia — specific doctor approval",
        "category": "prescription",
        "approval_types": ["specific"],
        "steps": [
            "Create prescription record",
            "ApprovalKit gate: healthcare-rx/prescribe (specific model)",
            "Guardian push → Dr. Smith approve",
            "Gmail → pharmacy notification (Token Vault)",
        ],
    },
    {
        "id": "controlled-substance",
        "title": "Controlled Substance",
        "description": "Prescribe Adderall 20mg — sequential: doctor → pharmacist",
        "category": "prescription",
        "approval_types": ["sequential"],
        "steps": [
            "Create controlled prescription (Schedule II)",
            "ApprovalKit gate: healthcare-rx/prescribe_controlled (sequential)",
            "First Guardian push → Dr. Smith approve",
            "Second Guardian push → Pharmacist approve",
            "Gmail → pharmacy notification",
        ],
    },
    {
        "id": "dose-change",
        "title": "Dose Change (Scope Creep)",
        "description": "Increase Metformin from 500mg to 1000mg — all_of_n + scope creep flag",
        "category": "prescription",
        "approval_types": ["all_of_n", "scope_creep"],
        "steps": [
            "Create dose change request",
            "Scope creep detection: first dose change flagged",
            "ApprovalKit gate: healthcare-rx/dose_change (all_of_n)",
            "Doctor + Pharmacist + CMO must all approve",
            "Gmail → patient notification + pharmacy update",
        ],
    },
    {
        "id": "external-referral",
        "title": "External Referral (HIPAA)",
        "description": "Refer Maria's blood tests to City General — doctor approval + Drive share",
        "category": "hipaa",
        "approval_types": ["specific"],
        "steps": [
            "Create referral record",
            "ApprovalKit gate: healthcare-hipaa/external_referral (specific)",
            "Doctor approval via Guardian",
            "Google Drive share (Token Vault) — only relevant files",
            "Gmail → clinic notification",
            "Audit: what, to whom, when, why",
        ],
    },
    {
        "id": "insurance-data-partial",
        "title": "Insurance Data Request (Partial Approval)",
        "description": "BlueCross requests full records — doctor narrows to summary only",
        "category": "hipaa",
        "approval_types": ["all_of_n", "partial_approval"],
        "steps": [
            "Insurance requests data_scope='full'",
            "ApprovalKit gate: healthcare-hipaa/insurance_data (all_of_n, partial_approval=true)",
            "Patient rep + Doctor must approve",
            "Doctor modifies scope: full → summary",
            "Google Drive shares summary only",
        ],
    },
    {
        "id": "research-export-anomaly",
        "title": "Research Data Export (Amount Anomaly)",
        "description": "Stanford requests 150 patient records — sequential + anomaly flag",
        "category": "hipaa",
        "approval_types": ["sequential", "amount_anomaly"],
        "steps": [
            "Export request for 150 patients",
            "Amount anomaly: 100+ patients auto-flagged",
            "ApprovalKit gate: healthcare-hipaa/research_export (sequential)",
            "Ethics board → CMO → Hospital director (in order)",
            "Anonymized data shared via Drive",
        ],
    },
    {
        "id": "small-billing",
        "title": "Small Billing (Auto-Approve)",
        "description": "Process $200 blood test — auto-approved, no rule match",
        "category": "billing",
        "approval_types": ["auto (no rule match)"],
        "steps": [
            "Create billing record: $200",
            "ApprovalKit gate: healthcare-billing/charge — no rule matches",
            "Auto-approved (pre_approved status)",
            "Gmail → insurance claim",
        ],
    },
    {
        "id": "large-billing-stepup",
        "title": "Large Billing (Step-Up)",
        "description": "Process $35,000 cardiac surgery — step-up escalation",
        "category": "billing",
        "approval_types": ["step_up", "all_of_n"],
        "steps": [
            "Create billing record: $35,000",
            "ApprovalKit gate: healthcare-billing/charge",
            "Base rule matches ($500+): finance manager",
            "Step-up triggers ($25,000+): finance + director + CMO",
            "Slack #billing alert",
            "Gmail → insurance claim",
        ],
    },
    {
        "id": "insurance-appeal",
        "title": "Insurance Appeal",
        "description": "Appeal denied claim — doctor + finance (all_of_n)",
        "category": "billing",
        "approval_types": ["all_of_n"],
        "steps": [
            "File appeal on denied billing",
            "ApprovalKit gate: healthcare-billing/appeal (all_of_n)",
            "Doctor + Finance must both approve",
            "Gmail → appeal letter to insurance",
            "Slack #billing + #medical alert",
        ],
    },
    {
        "id": "emergency-access",
        "title": "Emergency Data Access",
        "description": "Ambulance needs Maria's allergy info — any_one, 2-min timeout",
        "category": "emergency",
        "approval_types": ["any_one", "timeout_override"],
        "steps": [
            "Emergency event created",
            "Slack #emergency alert (immediate)",
            "ApprovalKit gate: healthcare-emergency/emergency_access",
            "any_one model: first available doctor approves",
            "2-minute timeout (no blackout override)",
            "Google Drive → records shared immediately",
            "Special audit logging for emergency access",
        ],
    },
    {
        "id": "security-breach",
        "title": "Security Breach",
        "description": "Unauthorized access detected — auto-freeze + security + CMO approval",
        "category": "emergency",
        "approval_types": ["all_of_n", "auto_freeze"],
        "steps": [
            "Account auto-frozen (immediate)",
            "Slack #security alert (immediate)",
            "ApprovalKit gate: healthcare-emergency/security_freeze (all_of_n)",
            "Security officer + CMO must both approve",
            "Gmail → patient security notice",
        ],
    },
    {
        "id": "doctor-delegation",
        "title": "Doctor Vacation Delegation",
        "description": "Dr. Smith on leave — delegate to Dr. Jones, update shifts + notify patients",
        "category": "staff",
        "approval_types": ["delegation"],
        "steps": [
            "Set delegation: Dr. Smith → Dr. Jones",
            "Update all future shifts",
            "Slack #medical announcement",
            "Gmail → patient notifications",
            "Google Calendar → shift updates",
        ],
    },
    {
        "id": "staff-access-stepup",
        "title": "New Staff Access (Step-Up)",
        "description": "New nurse requests medication system access — escalates through step-up",
        "category": "staff",
        "approval_types": ["specific", "step_up", "all_of_n"],
        "steps": [
            "Access request: medication_system",
            "ApprovalKit gate: healthcare-hr/access_change",
            "Step-up from IT-only to all_of_n (IT + pharmacy lead + CMO)",
            "Gmail → welcome email + access confirmation",
            "Slack #onboarding",
        ],
    },
]


@router.get("")
async def list_scenarios():
    return SCENARIOS


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    return scenario


async def _get_maria(db):
    result = await db.execute(select(Patient).where(Patient.mrn == "MRN-00001"))
    return result.scalar_one_or_none()


async def _get_first_doctor(db, specialty=None):
    q = select(Doctor).where(Doctor.is_active == True)
    if specialty:
        q = q.where(Doctor.specialty == specialty)
    result = await db.execute(q.limit(1))
    return result.scalar_one_or_none()


async def _get_cmo(db):
    result = await db.execute(select(Doctor).where(Doctor.is_cmo == True).limit(1))
    return result.scalar_one_or_none()


async def _get_staff_by_role(db, role):
    result = await db.execute(select(Staff).where(Staff.role == role).limit(1))
    return result.scalar_one_or_none()


async def _run_scenario(scenario_id: str):
    """Execute scenario in background."""
    async with async_session() as db:
        try:
            if scenario_id == "patient-onboarding":
                doctor = await _get_first_doctor(db, "Internal Medicine")
                insurance = await db.execute(select(InsuranceProvider).limit(1))
                ins = insurance.scalar_one_or_none()
                await PatientService.register_patient(db, {
                    "first_name": "Maria", "last_name": "Garcia",
                    "date_of_birth": "1985-03-15", "gender": "female",
                    "phone": "(555) 234-5678", "email": "maria.garcia@email.com",
                    "blood_type": "A+", "allergies": ["Penicillin"],
                    "conditions": ["Type 2 Diabetes Mellitus", "Essential Hypertension"],
                    "primary_doctor_id": str(doctor.id) if doctor else None,
                    "insurance_id": str(ins.id) if ins else None,
                    "insurance_policy_number": "POL-123456",
                })

            elif scenario_id == "routine-prescription":
                maria = await _get_maria(db)
                doctor = await _get_first_doctor(db, "Internal Medicine")
                if maria and doctor:
                    await PrescriptionService.create_prescription(db, {
                        "patient_id": str(maria.id),
                        "prescribing_doctor_id": str(doctor.id),
                        "medication_name": "Metformin",
                        "medication_code": "NDC-0093-7212",
                        "dosage": "500mg",
                        "frequency": "twice daily",
                        "quantity": 60,
                        "refills": 3,
                        "is_controlled": False,
                    })

            elif scenario_id == "controlled-substance":
                maria = await _get_maria(db)
                doctor = await _get_first_doctor(db, "Psychiatry")
                if maria and doctor:
                    await PrescriptionService.create_prescription(db, {
                        "patient_id": str(maria.id),
                        "prescribing_doctor_id": str(doctor.id),
                        "medication_name": "Adderall",
                        "medication_code": "NDC-0555-0768",
                        "dosage": "20mg",
                        "frequency": "once daily",
                        "quantity": 30,
                        "refills": 0,
                        "is_controlled": True,
                        "schedule_class": "II",
                    })

            elif scenario_id == "dose-change":
                maria = await _get_maria(db)
                doctor = await _get_first_doctor(db, "Internal Medicine")
                if maria:
                    result = await db.execute(
                        select(Prescription)
                        .where(Prescription.patient_id == maria.id)
                        .where(Prescription.medication_name == "Metformin")
                        .limit(1)
                    )
                    rx = result.scalar_one_or_none()
                    if rx and doctor:
                        await PrescriptionService.request_dose_change(db, {
                            "prescription_id": str(rx.id),
                            "requested_by_doctor_id": str(doctor.id),
                            "new_dosage": "1000mg",
                            "reason": "Blood glucose levels not adequately controlled at current dosage",
                        })

            elif scenario_id == "external-referral":
                maria = await _get_maria(db)
                doctor = await _get_first_doctor(db)
                if maria and doctor:
                    await ReferralService.create_external_referral(db, {
                        "patient_id": str(maria.id),
                        "referring_doctor_id": str(doctor.id),
                        "clinic_name": "City General Hospital",
                        "clinic_email": "referrals@citygeneral.com",
                        "reason": "Blood test analysis — elevated HbA1c levels",
                        "data_scope": "summary",
                    })

            elif scenario_id == "insurance-data-partial":
                maria = await _get_maria(db)
                insurance = await db.execute(
                    select(InsuranceProvider).where(InsuranceProvider.name.contains("BlueCross")).limit(1)
                )
                ins = insurance.scalar_one_or_none()
                if maria and ins:
                    await ReferralService.create_insurance_data_request(db, {
                        "patient_id": str(maria.id),
                        "insurance_provider_id": str(ins.id),
                        "requested_data_scope": "full",
                        "reason": "Annual coverage review and pre-authorization for upcoming treatments",
                    })

            elif scenario_id == "research-export-anomaly":
                doctor = await _get_first_doctor(db)
                patients = await db.execute(select(Patient.id).limit(150))
                patient_ids = [str(p[0]) for p in patients.all()]
                if doctor:
                    await ReferralService.create_research_export(db, {
                        "referring_doctor_id": str(doctor.id),
                        "research_entity_name": "Stanford Cardiology Research Lab",
                        "research_entity_email": "research@stanford.edu",
                        "reason": "Longitudinal study on Type 2 Diabetes and cardiovascular outcomes",
                        "patient_ids": patient_ids,
                        "patient_count": 150,
                        "data_scope": "anonymized",
                    })

            elif scenario_id == "small-billing":
                maria = await _get_maria(db)
                if maria:
                    await BillingService.create_billing(db, {
                        "patient_id": str(maria.id),
                        "description": "Complete Blood Count (CBC)",
                        "procedure_code": "85025",
                        "amount": 200,
                        "insurance_covered": 160,
                    })

            elif scenario_id == "large-billing-stepup":
                maria = await _get_maria(db)
                if maria:
                    await BillingService.create_billing(db, {
                        "patient_id": str(maria.id),
                        "description": "Coronary Artery Bypass Surgery",
                        "procedure_code": "33533",
                        "amount": 35000,
                        "insurance_covered": 28000,
                    })

            elif scenario_id == "emergency-access":
                maria = await _get_maria(db)
                if maria:
                    await EmergencyService.request_emergency_access(db, {
                        "patient_id": str(maria.id),
                        "triggered_by": "paramedic.jones@ambulance.com",
                        "reason": "Patient in ambulance — need allergy information STAT",
                    })

            elif scenario_id == "security-breach":
                maria = await _get_maria(db)
                if maria:
                    await EmergencyService.report_security_breach(db, {
                        "patient_id": str(maria.id),
                        "triggered_by": "security.system@medcore-hospital.com",
                        "reason": "Unauthorized access attempt from unknown IP 203.0.113.42",
                        "severity": "critical",
                    })

            elif scenario_id == "doctor-delegation":
                doctor = await _get_first_doctor(db, "Internal Medicine")
                delegate = await _get_first_doctor(db, "Cardiology")
                if doctor and delegate:
                    await StaffService.set_delegation(db, str(doctor.id), {
                        "delegate_to_id": str(delegate.id),
                        "days": 14,
                        "reason": "Scheduled vacation",
                    })

            elif scenario_id == "staff-access-stepup":
                nurse = await _get_staff_by_role(db, "nurse")
                if nurse:
                    await StaffService.request_access_change(db, {
                        "staff_id": str(nurse.id),
                        "requested_access_level": "medication_system",
                        "reason": "Transferred to ICU — requires medication dispensing access",
                    })

            # Log scenario completion
            db.add(ActivityLog(
                event_type="scenario_completed",
                category="system",
                title=f"Scenario: {scenario_id}",
                description=f"Demo scenario '{scenario_id}' executed successfully",
                severity="info",
                extra_data={"scenario_id": scenario_id},
            ))
            await db.commit()

        except Exception as e:
            db.add(ActivityLog(
                event_type="scenario_failed",
                category="system",
                title=f"Scenario Failed: {scenario_id}",
                description=str(e),
                severity="error",
                extra_data={"scenario_id": scenario_id, "error": str(e)},
            ))
            await db.commit()


@router.post("/{scenario_id}/run")
async def run_scenario(scenario_id: str, background_tasks: BackgroundTasks):
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    background_tasks.add_task(_run_scenario, scenario_id)
    return {
        "scenario_id": scenario_id,
        "status": "running",
        "message": f"Scenario '{scenario['title']}' started in background",
    }
