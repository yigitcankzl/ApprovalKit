"""
Healthcare AI Agent — Seed Data Generator
Generates 50+ patients, 20+ doctors, 15+ staff, 5 insurance providers.
"""
import uuid
import random
from datetime import datetime, date, time, timedelta
from decimal import Decimal

from backend.seed.medical_data import (
    MEDICATIONS, CONDITIONS, ALLERGIES, BLOOD_TYPES, BLOOD_TYPE_WEIGHTS,
    SPECIALTIES, PROCEDURES,
)

# ── Name pools ──────────────────────────────────────────────────────────
FIRST_NAMES_F = [
    "Maria", "Sofia", "Emma", "Olivia", "Isabella", "Ava", "Mia", "Luna",
    "Charlotte", "Amelia", "Sophia", "Evelyn", "Harper", "Camila", "Gianna",
    "Abigail", "Ella", "Elizabeth", "Victoria", "Grace", "Chloe", "Penelope",
    "Layla", "Riley", "Zoey", "Nora", "Lily", "Eleanor", "Hannah", "Lillian",
]

FIRST_NAMES_M = [
    "James", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony",
    "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth",
    "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward", "Jason",
    "Jeffrey", "Ryan", "Jacob",
]

LAST_NAMES = [
    "Garcia", "Smith", "Johnson", "Williams", "Brown", "Jones", "Davis",
    "Miller", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
    "White", "Harris", "Martin", "Thompson", "Robinson", "Clark",
    "Lewis", "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright",
    "Lopez", "Hill", "Scott", "Green", "Adams", "Baker", "Gonzalez",
    "Nelson", "Carter", "Mitchell", "Perez", "Roberts", "Turner", "Phillips",
    "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Sanchez", "Morris",
]

CITIES = [
    ("New York", "NY", "10001"), ("Los Angeles", "CA", "90001"),
    ("Chicago", "IL", "60601"), ("Houston", "TX", "77001"),
    ("Phoenix", "AZ", "85001"), ("Philadelphia", "PA", "19101"),
    ("San Antonio", "TX", "78201"), ("San Diego", "CA", "92101"),
    ("Dallas", "TX", "75201"), ("Austin", "TX", "78701"),
    ("Boston", "MA", "02101"), ("Seattle", "WA", "98101"),
    ("Denver", "CO", "80201"), ("Miami", "FL", "33101"),
    ("Atlanta", "GA", "30301"),
]

STREETS = [
    "Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine Rd",
    "Elm St", "Washington Blvd", "Park Ave", "Lake Dr", "River Rd",
    "Highland Ave", "Forest Dr", "Sunset Blvd", "Broadway", "Spring St",
]

RELATIONSHIPS = ["Spouse", "Parent", "Sibling", "Child", "Friend"]


def _phone():
    return f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}"


def _ssn_masked():
    return f"***-**-{random.randint(1000,9999)}"


def _address():
    city, state, zip_code = random.choice(CITIES)
    return {
        "street": f"{random.randint(100,9999)} {random.choice(STREETS)}",
        "city": city,
        "state": state,
        "zip": zip_code,
    }


def _mrn(idx):
    return f"MRN-{idx:05d}"


def _npi(idx):
    return f"NPI-{1000000000 + idx}"


def _employee_id(idx):
    return f"EMP-{idx:04d}"


def _invoice(idx):
    return f"INV-{idx:06d}"


def _rx(idx):
    return f"RX-{idx:07d}"


# ── Insurance Providers ─────────────────────────────────────────────────

def generate_insurance_providers():
    providers = [
        {
            "id": str(uuid.uuid4()),
            "name": "BlueCross BlueShield",
            "plan_type": "PPO",
            "contact_email": "claims@bcbs.com",
            "phone": "(800) 262-2583",
            "coverage_details": {
                "deductible": 1500, "max_out_of_pocket": 6000,
                "coinsurance": 0.20, "copay_primary": 25, "copay_specialist": 50,
                "covers_mental_health": True, "covers_rx": True,
            },
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Aetna",
            "plan_type": "HMO",
            "contact_email": "claims@aetna.com",
            "phone": "(800) 872-3862",
            "coverage_details": {
                "deductible": 1000, "max_out_of_pocket": 5000,
                "coinsurance": 0.15, "copay_primary": 20, "copay_specialist": 40,
                "covers_mental_health": True, "covers_rx": True,
            },
        },
        {
            "id": str(uuid.uuid4()),
            "name": "UnitedHealthcare",
            "plan_type": "EPO",
            "contact_email": "claims@uhc.com",
            "phone": "(800) 328-5979",
            "coverage_details": {
                "deductible": 2000, "max_out_of_pocket": 7000,
                "coinsurance": 0.25, "copay_primary": 30, "copay_specialist": 60,
                "covers_mental_health": True, "covers_rx": True,
            },
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Cigna",
            "plan_type": "PPO",
            "contact_email": "claims@cigna.com",
            "phone": "(800) 244-6224",
            "coverage_details": {
                "deductible": 1200, "max_out_of_pocket": 5500,
                "coinsurance": 0.20, "copay_primary": 25, "copay_specialist": 45,
                "covers_mental_health": True, "covers_rx": True,
            },
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Medicare",
            "plan_type": "POS",
            "contact_email": "claims@medicare.gov",
            "phone": "(800) 633-4227",
            "coverage_details": {
                "deductible": 233, "max_out_of_pocket": 0,
                "coinsurance": 0.20, "copay_primary": 0, "copay_specialist": 0,
                "covers_mental_health": True, "covers_rx": True,
                "part_d": True,
            },
        },
    ]
    return providers


# ── Doctors ─────────────────────────────────────────────────────────────

def generate_doctors():
    doctor_specs = [
        ("Robert", "Chen", "Cardiology", "Cardiology", True, False),
        ("Sarah", "Williams", "Cardiology", "Cardiology", False, False),
        ("Ahmed", "Patel", "Cardiology", "Cardiology", False, False),
        ("Jennifer", "Kim", "Oncology", "Oncology", False, False),
        ("David", "Martinez", "Oncology", "Oncology", False, False),
        ("Lisa", "Thompson", "Oncology", "Oncology", False, False),
        ("Michael", "Johnson", "Neurology", "Neurology", False, False),
        ("Emily", "Davis", "Neurology", "Neurology", False, False),
        ("James", "Wilson", "General Surgery", "Surgery", False, False),
        ("Patricia", "Moore", "General Surgery", "Surgery", False, False),
        ("Richard", "Anderson", "Psychiatry", "Psychiatry", False, False),
        ("Karen", "Taylor", "Psychiatry", "Psychiatry", False, False),
        ("Daniel", "Brown", "Pediatrics", "Pediatrics", False, False),
        ("Susan", "Garcia", "Pediatrics", "Pediatrics", False, False),
        ("Christopher", "Lee", "Internal Medicine", "Internal Medicine", False, False),
        ("Nancy", "Clark", "Internal Medicine", "Internal Medicine", False, False),
        ("Thomas", "Rodriguez", "Emergency Medicine", "Emergency", False, False),
        ("Margaret", "Lewis", "Emergency Medicine", "Emergency", False, False),
        ("William", "Harris", "Endocrinology", "Endocrinology", False, False),
        ("Elizabeth", "Young", "Pulmonology", "Pulmonology", False, False),
        ("Joseph", "Walker", "Nephrology", "Nephrology", False, False),
        ("Sandra", "Allen", "Orthopedics", "Orthopedics", False, False),
        ("George", "Wright", "Radiology", "Radiology", False, False),
        ("Dorothy", "King", "Gastroenterology", "Gastroenterology", False, True),
    ]

    doctors = []
    for i, (first, last, spec, dept, is_cmo, on_vac) in enumerate(doctor_specs):
        doctors.append({
            "id": str(uuid.uuid4()),
            "npi": _npi(i + 1),
            "first_name": first,
            "last_name": last,
            "email": f"dr.{first.lower()}.{last.lower()}@medcore-hospital.com",
            "phone": _phone(),
            "specialty": spec,
            "department": dept,
            "license_number": f"MD-{random.randint(100000,999999)}",
            "is_cmo": is_cmo,
            "is_active": True,
            "on_vacation": on_vac,
            "delegate_to_id": None,
            "delegate_until": None,
        })

    # Dr. King (on vacation) delegates to Dr. Walker
    if doctors[-1]["on_vacation"]:
        doctors[-1]["delegate_to_id"] = doctors[-2]["id"]
        doctors[-1]["delegate_until"] = (datetime.utcnow() + timedelta(days=14)).isoformat()

    return doctors


# ── Staff ───────────────────────────────────────────────────────────────

def generate_staff():
    staff_specs = [
        ("Michael", "Torres", "pharmacist", "Pharmacy", "medication_system", True),
        ("Angela", "Rivera", "pharmacist", "Pharmacy", "medication_system", False),
        ("Carlos", "Flores", "pharmacist", "Pharmacy", "medication_system", False),
        ("Diana", "Hughes", "nurse", "Internal Medicine", "patient_records", False),
        ("Elena", "Cooper", "nurse", "Emergency", "patient_records", False),
        ("Frank", "Reed", "nurse", "Cardiology", "patient_records", False),
        ("Gloria", "Butler", "nurse", "Oncology", "patient_records", False),
        ("Henry", "Brooks", "it_admin", "IT", "full", False),
        ("Irene", "Price", "it_admin", "IT", "full", False),
        ("Jack", "Bennett", "finance_manager", "Finance", "basic", False),
        ("Katherine", "Gray", "finance_staff", "Finance", "basic", False),
        ("Leonard", "Diaz", "security_officer", "Security", "full", False),
        ("Martha", "Sanders", "ethics_board", "Administration", "basic", False),
        ("Nathan", "Powell", "hospital_director", "Administration", "full", False),
        ("Olivia", "Russell", "patient_representative", "Administration", "patient_records", False),
        ("Peter", "Foster", "nurse", "Surgery", "patient_records", False),
    ]

    staff = []
    for i, (first, last, role, dept, access, is_pharmacy_lead) in enumerate(staff_specs):
        s = {
            "id": str(uuid.uuid4()),
            "employee_id": _employee_id(i + 1),
            "first_name": first,
            "last_name": last,
            "email": f"{first.lower()}.{last.lower()}@medcore-hospital.com",
            "phone": _phone(),
            "role": role,
            "department": dept,
            "access_level": access,
            "is_active": True,
        }
        if is_pharmacy_lead:
            s["role"] = "pharmacy_lead"
        staff.append(s)
    return staff


# ── Patients ────────────────────────────────────────────────────────────

def generate_patients(doctor_ids: list[str], insurance_ids: list[str]):
    patients = []
    all_first = FIRST_NAMES_F + FIRST_NAMES_M
    used_names = set()

    for i in range(55):
        gender = random.choice(["male", "female"])
        if gender == "female":
            first = random.choice(FIRST_NAMES_F)
        else:
            first = random.choice(FIRST_NAMES_M)
        last = random.choice(LAST_NAMES)

        key = f"{first}_{last}"
        while key in used_names:
            last = random.choice(LAST_NAMES)
            key = f"{first}_{last}"
        used_names.add(key)

        age = random.randint(18, 90)
        dob = date.today() - timedelta(days=age * 365 + random.randint(0, 364))

        num_conditions = random.choices([0, 1, 2, 3, 4], weights=[0.1, 0.3, 0.3, 0.2, 0.1])[0]
        patient_conditions = random.sample(
            [c["name"] for c in CONDITIONS], min(num_conditions, len(CONDITIONS))
        )

        num_allergies = random.choices([0, 1, 2, 3], weights=[0.4, 0.3, 0.2, 0.1])[0]
        patient_allergies = random.sample(ALLERGIES, min(num_allergies, len(ALLERGIES)))

        blood_type = random.choices(BLOOD_TYPES, weights=BLOOD_TYPE_WEIGHTS)[0]

        contact_first = random.choice(all_first)
        contact_last = random.choice(LAST_NAMES)

        status = random.choices(
            ["active", "discharged", "admitted"],
            weights=[0.7, 0.2, 0.1],
        )[0]

        # Assign current medications based on conditions
        current_meds = []
        for cond in patient_conditions:
            if "Diabetes" in cond:
                current_meds.append("Metformin 500mg")
            elif "Hypertension" in cond:
                current_meds.append("Lisinopril 10mg")
            elif "Asthma" in cond:
                current_meds.append("Albuterol inhaler")
            elif "Depression" in cond:
                current_meds.append("Sertraline 50mg")
            elif "Hypothyroidism" in cond:
                current_meds.append("Levothyroxine 50mcg")

        patients.append({
            "id": str(uuid.uuid4()),
            "mrn": _mrn(i + 1),
            "first_name": first,
            "last_name": last,
            "date_of_birth": dob.isoformat(),
            "gender": gender,
            "ssn_masked": _ssn_masked(),
            "phone": _phone(),
            "email": f"{first.lower()}.{last.lower()}@email.com",
            "address": _address(),
            "emergency_contact": {
                "name": f"{contact_first} {contact_last}",
                "phone": _phone(),
                "relationship": random.choice(RELATIONSHIPS),
            },
            "blood_type": blood_type,
            "allergies": patient_allergies,
            "conditions": patient_conditions,
            "medications_current": current_meds,
            "primary_doctor_id": random.choice(doctor_ids),
            "insurance_id": random.choice(insurance_ids),
            "insurance_policy_number": f"POL-{random.randint(100000, 999999)}",
            "status": status,
            "admitted_at": datetime.utcnow().isoformat() if status == "admitted" else None,
            "notes": None,
        })

    # Ensure our key demo patient Maria Garcia is first
    patients[0]["first_name"] = "Maria"
    patients[0]["last_name"] = "Garcia"
    patients[0]["mrn"] = "MRN-00001"
    patients[0]["conditions"] = ["Type 2 Diabetes Mellitus", "Essential Hypertension"]
    patients[0]["allergies"] = ["Penicillin"]
    patients[0]["medications_current"] = ["Metformin 500mg", "Lisinopril 10mg"]
    patients[0]["status"] = "active"
    patients[0]["email"] = "maria.garcia@email.com"

    return patients


# ── Appointments ────────────────────────────────────────────────────────

def generate_appointments(patient_ids: list[str], doctor_ids: list[str]):
    appointments = []
    types = ["initial", "followup", "specialist", "checkup", "lab_review"]
    locations = [
        "Main Building, Room 101", "Main Building, Room 205",
        "East Wing, Room 302", "West Wing, Room 110",
        "Outpatient Center, Room 3", "Cardiology Suite, Room 2",
    ]

    for i in range(40):
        days_offset = random.randint(-30, 60)
        hour = random.randint(8, 17)
        sched = datetime.utcnow().replace(hour=hour, minute=random.choice([0, 15, 30, 45])) + timedelta(days=days_offset)
        status = "completed" if days_offset < 0 else "scheduled"

        appointments.append({
            "id": str(uuid.uuid4()),
            "patient_id": random.choice(patient_ids),
            "doctor_id": random.choice(doctor_ids),
            "appointment_type": random.choice(types),
            "scheduled_at": sched.isoformat(),
            "duration_minutes": random.choice([15, 30, 45, 60]),
            "location": random.choice(locations),
            "status": status,
            "notes": None,
        })
    return appointments


# ── Billing Records ─────────────────────────────────────────────────────

def generate_billing_records(patient_ids: list[str]):
    records = []
    for i in range(30):
        proc = random.choice(PROCEDURES)
        amount = Decimal(str(proc["typical_cost"])) * Decimal(str(random.uniform(0.8, 1.3)))
        amount = amount.quantize(Decimal("0.01"))
        insurance_pct = Decimal(str(random.uniform(0.5, 0.9)))
        insurance_covered = (amount * insurance_pct).quantize(Decimal("0.01"))
        patient_resp = amount - insurance_covered

        status = random.choices(
            ["paid", "pending", "approved", "denied"],
            weights=[0.5, 0.2, 0.2, 0.1],
        )[0]

        records.append({
            "id": str(uuid.uuid4()),
            "invoice_number": _invoice(i + 1),
            "patient_id": random.choice(patient_ids),
            "description": proc["name"],
            "procedure_code": proc["code"],
            "amount": str(amount),
            "insurance_covered": str(insurance_covered),
            "patient_responsibility": str(patient_resp),
            "status": status,
            "notes": None,
        })
    return records


# ── Shift Schedule ──────────────────────────────────────────────────────

def generate_shifts(doctor_ids: list[str]):
    shifts = []
    departments = ["Emergency", "Internal Medicine", "Cardiology", "Surgery", "ICU"]

    for i in range(60):
        day_offset = random.randint(-7, 30)
        shift_d = date.today() + timedelta(days=day_offset)
        start = random.choice([time(7, 0), time(15, 0), time(23, 0)])
        end = time((start.hour + 8) % 24, 0)

        shifts.append({
            "id": str(uuid.uuid4()),
            "doctor_id": random.choice(doctor_ids),
            "shift_date": shift_d.isoformat(),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "department": random.choice(departments),
            "status": "scheduled",
        })
    return shifts


# ── Prescriptions ───────────────────────────────────────────────────────

def generate_prescriptions(patient_ids: list[str], doctor_ids: list[str]):
    prescriptions = []
    for i in range(25):
        med = random.choice(MEDICATIONS)
        patient_id = random.choice(patient_ids)
        status = random.choices(
            ["approved", "dispensed", "pending_approval"],
            weights=[0.4, 0.4, 0.2],
        )[0]

        prescriptions.append({
            "id": str(uuid.uuid4()),
            "rx_number": _rx(i + 1),
            "patient_id": patient_id,
            "prescribing_doctor_id": random.choice(doctor_ids),
            "medication_name": med["name"],
            "medication_code": med["code"],
            "dosage": med["common_dosage"],
            "frequency": random.choice(["once daily", "twice daily", "three times daily", "as needed"]),
            "quantity": random.choice([14, 30, 60, 90]),
            "refills": random.randint(0, 6),
            "is_controlled": med["controlled"],
            "schedule_class": med.get("schedule"),
            "status": status,
            "approved_by_doctor": status in ("approved", "dispensed"),
            "approved_by_pharmacist": status == "dispensed" and med["controlled"],
            "approved_by_cmo": False,
            "pharmacy_email": "pharmacy@medcore-hospital.com",
            "notes": None,
        })
    return prescriptions


# ── Master Generator ────────────────────────────────────────────────────

def generate_all():
    """Generate all seed data and return as a dictionary."""
    insurance_providers = generate_insurance_providers()
    insurance_ids = [p["id"] for p in insurance_providers]

    doctors = generate_doctors()
    doctor_ids = [d["id"] for d in doctors]

    staff = generate_staff()

    patients = generate_patients(doctor_ids, insurance_ids)
    patient_ids = [p["id"] for p in patients]

    appointments = generate_appointments(patient_ids, doctor_ids)
    billing_records = generate_billing_records(patient_ids)
    shifts = generate_shifts(doctor_ids)
    prescriptions = generate_prescriptions(patient_ids, doctor_ids)

    return {
        "insurance_providers": insurance_providers,
        "doctors": doctors,
        "staff": staff,
        "patients": patients,
        "appointments": appointments,
        "billing_records": billing_records,
        "shifts": shifts,
        "prescriptions": prescriptions,
    }
