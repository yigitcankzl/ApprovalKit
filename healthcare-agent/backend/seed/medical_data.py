"""
Medical reference data — medications, conditions, ICD codes, procedures.
"""

MEDICATIONS = [
    {"name": "Metformin", "code": "NDC-0093-7212", "class": "Biguanide", "common_dosage": "500mg", "controlled": False},
    {"name": "Lisinopril", "code": "NDC-0093-7339", "class": "ACE Inhibitor", "common_dosage": "10mg", "controlled": False},
    {"name": "Atorvastatin", "code": "NDC-0071-0155", "class": "Statin", "common_dosage": "20mg", "controlled": False},
    {"name": "Amlodipine", "code": "NDC-0069-1530", "class": "Calcium Channel Blocker", "common_dosage": "5mg", "controlled": False},
    {"name": "Omeprazole", "code": "NDC-0186-5020", "class": "Proton Pump Inhibitor", "common_dosage": "20mg", "controlled": False},
    {"name": "Levothyroxine", "code": "NDC-0074-9295", "class": "Thyroid Hormone", "common_dosage": "50mcg", "controlled": False},
    {"name": "Albuterol", "code": "NDC-0173-0682", "class": "Bronchodilator", "common_dosage": "90mcg inhaler", "controlled": False},
    {"name": "Losartan", "code": "NDC-0093-7365", "class": "ARB", "common_dosage": "50mg", "controlled": False},
    {"name": "Gabapentin", "code": "NDC-0071-0803", "class": "Anticonvulsant", "common_dosage": "300mg", "controlled": False},
    {"name": "Sertraline", "code": "NDC-0049-4900", "class": "SSRI", "common_dosage": "50mg", "controlled": False},
    {"name": "Fluoxetine", "code": "NDC-0777-3105", "class": "SSRI", "common_dosage": "20mg", "controlled": False},
    {"name": "Prednisone", "code": "NDC-0054-4728", "class": "Corticosteroid", "common_dosage": "10mg", "controlled": False},
    {"name": "Montelukast", "code": "NDC-0006-0117", "class": "Leukotriene Modifier", "common_dosage": "10mg", "controlled": False},
    {"name": "Insulin Glargine", "code": "NDC-0024-5210", "class": "Insulin", "common_dosage": "100 units/mL", "controlled": False},
    {"name": "Warfarin", "code": "NDC-0056-0169", "class": "Anticoagulant", "common_dosage": "5mg", "controlled": False},
    {"name": "Clopidogrel", "code": "NDC-0074-3084", "class": "Antiplatelet", "common_dosage": "75mg", "controlled": False},
    {"name": "Metoprolol", "code": "NDC-0093-7329", "class": "Beta Blocker", "common_dosage": "50mg", "controlled": False},
    {"name": "Pantoprazole", "code": "NDC-0008-0841", "class": "Proton Pump Inhibitor", "common_dosage": "40mg", "controlled": False},
    {"name": "Furosemide", "code": "NDC-0054-4299", "class": "Loop Diuretic", "common_dosage": "40mg", "controlled": False},
    {"name": "Amoxicillin", "code": "NDC-0093-4150", "class": "Antibiotic", "common_dosage": "500mg", "controlled": False},
    # Controlled substances
    {"name": "Adderall", "code": "NDC-0555-0768", "class": "Amphetamine", "common_dosage": "20mg", "controlled": True, "schedule": "II"},
    {"name": "Oxycodone", "code": "NDC-0591-0266", "class": "Opioid", "common_dosage": "5mg", "controlled": True, "schedule": "II"},
    {"name": "Morphine Sulfate", "code": "NDC-0054-0235", "class": "Opioid", "common_dosage": "15mg", "controlled": True, "schedule": "II"},
    {"name": "Fentanyl Patch", "code": "NDC-0591-3765", "class": "Opioid", "common_dosage": "25mcg/hr", "controlled": True, "schedule": "II"},
    {"name": "Methylphenidate", "code": "NDC-0093-5803", "class": "Stimulant", "common_dosage": "10mg", "controlled": True, "schedule": "II"},
    {"name": "Alprazolam", "code": "NDC-0009-0029", "class": "Benzodiazepine", "common_dosage": "0.5mg", "controlled": True, "schedule": "IV"},
    {"name": "Diazepam", "code": "NDC-0140-0005", "class": "Benzodiazepine", "common_dosage": "5mg", "controlled": True, "schedule": "IV"},
    {"name": "Zolpidem", "code": "NDC-0024-5401", "class": "Sedative", "common_dosage": "10mg", "controlled": True, "schedule": "IV"},
    {"name": "Tramadol", "code": "NDC-0093-0058", "class": "Opioid", "common_dosage": "50mg", "controlled": True, "schedule": "IV"},
    {"name": "Codeine/Acetaminophen", "code": "NDC-0591-0524", "class": "Opioid Combination", "common_dosage": "30mg/300mg", "controlled": True, "schedule": "III"},
]

CONDITIONS = [
    {"name": "Type 2 Diabetes Mellitus", "icd10": "E11.9", "category": "endocrine"},
    {"name": "Essential Hypertension", "icd10": "I10", "category": "cardiovascular"},
    {"name": "Hyperlipidemia", "icd10": "E78.5", "category": "metabolic"},
    {"name": "Coronary Artery Disease", "icd10": "I25.10", "category": "cardiovascular"},
    {"name": "Atrial Fibrillation", "icd10": "I48.91", "category": "cardiovascular"},
    {"name": "Congestive Heart Failure", "icd10": "I50.9", "category": "cardiovascular"},
    {"name": "Asthma", "icd10": "J45.909", "category": "respiratory"},
    {"name": "COPD", "icd10": "J44.1", "category": "respiratory"},
    {"name": "Major Depressive Disorder", "icd10": "F33.0", "category": "psychiatric"},
    {"name": "Generalized Anxiety Disorder", "icd10": "F41.1", "category": "psychiatric"},
    {"name": "ADHD", "icd10": "F90.0", "category": "psychiatric"},
    {"name": "Chronic Kidney Disease Stage 3", "icd10": "N18.3", "category": "renal"},
    {"name": "Rheumatoid Arthritis", "icd10": "M06.9", "category": "musculoskeletal"},
    {"name": "Osteoarthritis", "icd10": "M19.90", "category": "musculoskeletal"},
    {"name": "Hypothyroidism", "icd10": "E03.9", "category": "endocrine"},
    {"name": "Epilepsy", "icd10": "G40.909", "category": "neurological"},
    {"name": "Migraine", "icd10": "G43.909", "category": "neurological"},
    {"name": "GERD", "icd10": "K21.0", "category": "gastrointestinal"},
    {"name": "Iron Deficiency Anemia", "icd10": "D50.9", "category": "hematological"},
    {"name": "Obesity", "icd10": "E66.9", "category": "metabolic"},
]

PROCEDURES = [
    {"name": "Office Visit — New Patient", "code": "99203", "typical_cost": 250},
    {"name": "Office Visit — Established", "code": "99213", "typical_cost": 150},
    {"name": "Comprehensive Metabolic Panel", "code": "80053", "typical_cost": 45},
    {"name": "Complete Blood Count", "code": "85025", "typical_cost": 35},
    {"name": "Hemoglobin A1C", "code": "83036", "typical_cost": 55},
    {"name": "Lipid Panel", "code": "80061", "typical_cost": 40},
    {"name": "Chest X-Ray", "code": "71046", "typical_cost": 180},
    {"name": "MRI Brain", "code": "70553", "typical_cost": 450},
    {"name": "MRI Spine", "code": "72148", "typical_cost": 480},
    {"name": "CT Scan Abdomen", "code": "74177", "typical_cost": 380},
    {"name": "Echocardiogram", "code": "93306", "typical_cost": 350},
    {"name": "EKG/ECG", "code": "93000", "typical_cost": 85},
    {"name": "Colonoscopy", "code": "45378", "typical_cost": 1200},
    {"name": "Upper Endoscopy", "code": "43239", "typical_cost": 950},
    {"name": "Cardiac Catheterization", "code": "93458", "typical_cost": 5500},
    {"name": "Coronary Artery Bypass", "code": "33533", "typical_cost": 35000},
    {"name": "Hip Replacement", "code": "27130", "typical_cost": 28000},
    {"name": "Knee Replacement", "code": "27447", "typical_cost": 25000},
    {"name": "Appendectomy", "code": "44970", "typical_cost": 12000},
    {"name": "Physical Therapy Session", "code": "97110", "typical_cost": 120},
]

ALLERGIES = [
    "Penicillin", "Sulfa drugs", "Aspirin", "Ibuprofen", "Codeine",
    "Latex", "Shellfish", "Peanuts", "Tree nuts", "Eggs",
    "Contrast dye", "Lidocaine", "Morphine", "Tetracycline", "Cephalosporins",
]

BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
BLOOD_TYPE_WEIGHTS = [0.34, 0.06, 0.09, 0.02, 0.03, 0.01, 0.38, 0.07]

SPECIALTIES = [
    "Cardiology", "Oncology", "Neurology", "General Surgery",
    "Psychiatry", "Pediatrics", "Internal Medicine", "Emergency Medicine",
    "Endocrinology", "Pulmonology", "Nephrology", "Orthopedics",
    "Radiology", "Gastroenterology", "Rheumatology",
]

DEPARTMENTS = [
    "Cardiology", "Oncology", "Neurology", "Surgery",
    "Psychiatry", "Pediatrics", "Internal Medicine", "Emergency",
    "Endocrinology", "Pulmonology", "Nephrology", "Orthopedics",
    "Radiology", "Gastroenterology", "Pharmacy", "IT",
    "Finance", "Administration", "Security", "Human Resources",
]
