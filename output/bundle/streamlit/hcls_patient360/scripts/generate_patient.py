"""Synthetic Patient Generator for HCLS Patient 360."""
import snowflake.connector
import json
import random
from datetime import datetime, timedelta
import os

FIRST_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer",
               "Michael", "Linda", "David", "Elizabeth", "William", "Barbara",
               "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
               "Christopher", "Lisa", "Daniel", "Nancy", "Charles", "Karen"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
              "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
              "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore"]
GENDERS = ["Male", "Female"]
ETHNICITIES = ["Caucasian", "African American", "Hispanic", "Asian", "Other"]
REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West"]
INSURANCE_TYPES = ["Medicare", "Medicaid", "Commercial", "Self-Pay", "VA"]

DIAGNOSES = [
    ("E11.9", "Type 2 diabetes mellitus without complications", 1),
    ("I25.10", "Atherosclerotic heart disease", 1),
    ("I50.9", "Heart failure, unspecified", 1),
    ("I48.0", "Paroxysmal atrial fibrillation", 1),
    ("N18.3", "Chronic kidney disease, stage 3", 2),
    ("J44.1", "COPD with acute exacerbation", 1),
    ("J45.20", "Mild intermittent asthma", 1),
    ("I10", "Essential hypertension", 0),
    ("F32.1", "Major depressive disorder", 0),
    ("E66.01", "Morbid obesity", 0),
    ("E78.5", "Hyperlipidemia", 0),
    ("E03.9", "Hypothyroidism", 0),
]

MEDICATIONS = [
    ("Metformin", "500mg BID"), ("Lisinopril", "10mg daily"), ("Atorvastatin", "40mg daily"),
    ("Amlodipine", "5mg daily"), ("Metoprolol", "25mg BID"), ("Omeprazole", "20mg daily"),
    ("Albuterol", "2 puffs PRN"), ("Warfarin", "5mg daily"), ("Insulin Glargine", "20 units QHS"),
    ("Furosemide", "40mg daily"), ("Gabapentin", "300mg TID"), ("Sertraline", "50mg daily"),
]

LAB_TESTS = [
    ("HbA1c", "%", "4.0-5.6", 4.5, 12.0),
    ("LDL Cholesterol", "mg/dL", "<100", 60, 200),
    ("Creatinine", "mg/dL", "0.7-1.3", 0.5, 4.0),
    ("eGFR", "mL/min", ">60", 20, 120),
    ("TSH", "mIU/L", "0.4-4.0", 0.2, 10.0),
    ("WBC", "K/uL", "4.5-11.0", 3.0, 15.0),
    ("Hemoglobin", "g/dL", "12.0-17.5", 8.0, 17.0),
    ("Blood Glucose", "mg/dL", "70-100", 60, 300),
    ("BNP", "pg/mL", "<100", 10, 500),
]

ENCOUNTER_TYPES = ["Emergency", "Inpatient", "Outpatient", "Observation", "Telehealth"]
DEPARTMENTS = ["Primary Care", "Cardiology", "Emergency", "Surgery", "Oncology", "Radiology"]


def generate_and_insert(conn=None):
    owns_conn = conn is None
    if owns_conn:
        conn_name = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME") or "default"
        conn = snowflake.connector.connect(
            connection_name=conn_name,
            client_store_temporary_credential=False,
        )
    cur = conn.cursor()
    cur.execute("USE DATABASE HCLS_PATIENT360")
    cur.execute("USE SCHEMA PUBLIC")

    pid = f"P{random.randint(10000, 99999)}"
    fname = random.choice(FIRST_NAMES)
    lname = random.choice(LAST_NAMES)
    age = random.randint(25, 92)
    gender = random.choice(GENDERS)

    cur.execute("""
        INSERT INTO PATIENTS (PATIENT_ID, FIRST_NAME, LAST_NAME, AGE, GENDER, ETHNICITY, REGION, INSURANCE_TYPE)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, [pid, fname, lname, age, gender,
          random.choice(ETHNICITIES), random.choice(REGIONS), random.choice(INSURANCE_TYPES)])

    # Encounters
    n_enc = random.randint(3, 8)
    enc_ids = []
    for _ in range(n_enc):
        eid = f"E{random.randint(100000, 999999)}"
        enc_ids.append(eid)
        etype = random.choice(ENCOUNTER_TYPES)
        los = random.randint(1, 12) if etype == "Inpatient" else 0
        cur.execute("""
            INSERT INTO ENCOUNTERS (ENCOUNTER_ID, PATIENT_ID, ENCOUNTER_DATE, ENCOUNTER_TYPE,
                                    PROVIDER_ID, DEPARTMENT, LENGTH_OF_STAY)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, [eid, pid,
              (datetime.now() - timedelta(days=random.randint(1, 700))).strftime("%Y-%m-%d"),
              etype, f"DR{random.randint(0, 29):04d}", random.choice(DEPARTMENTS), los])

    # Diagnoses
    patient_dx = random.sample(DIAGNOSES, random.randint(2, 6))
    for code, desc, _ in patient_dx:
        cur.execute("""
            INSERT INTO DIAGNOSES (DIAGNOSIS_ID, ENCOUNTER_ID, ICD10_CODE, DESCRIPTION, SEVERITY)
            VALUES (%s, %s, %s, %s, %s)
        """, [f"D{random.randint(100000, 999999)}", random.choice(enc_ids),
              code, desc, random.choice(["Mild", "Moderate", "Severe"])])

    # Medications
    patient_meds = random.sample(MEDICATIONS, random.randint(2, 6))
    for drug, dosage in patient_meds:
        end = None if random.random() > 0.3 else (datetime.now() - timedelta(days=random.randint(1, 60))).strftime("%Y-%m-%d")
        cur.execute("""
            INSERT INTO MEDICATIONS (MEDICATION_ID, PATIENT_ID, DRUG_NAME, DOSAGE, START_DATE, END_DATE, ADHERENCE)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, [f"M{random.randint(100000, 999999)}", pid, drug, dosage,
              (datetime.now() - timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d"),
              end, round(random.uniform(0.5, 1.0), 2)])

    # Labs
    patient_labs = random.sample(LAB_TESTS, random.randint(4, 8))
    for test, unit, ref, lo, hi in patient_labs:
        val = round(random.uniform(lo, hi), 1)
        abnormal = None
        if "-" in ref:
            parts = ref.split("-")
            rlo, rhi = float(parts[0]), float(parts[1])
            if val > rhi:
                abnormal = "H"
            elif val < rlo:
                abnormal = "L"
        elif ref.startswith("<") and val > float(ref[1:]):
            abnormal = "H"
        elif ref.startswith(">") and val < float(ref[1:]):
            abnormal = "L"
        cur.execute("""
            INSERT INTO LAB_RESULTS (LAB_ID, PATIENT_ID, TEST_NAME, RESULT_VALUE, UNIT,
                                     REFERENCE_RANGE, LAB_DATE, ABNORMAL_FLAG)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, [f"L{random.randint(100000, 999999)}", pid, test, val, unit, ref,
              (datetime.now() - timedelta(days=random.randint(1, 180))).strftime("%Y-%m-%d"), abnormal])

    # Claims
    for _ in range(random.randint(1, 4)):
        status = random.choice(["Paid", "Paid", "Paid", "Denied", "Pending"])
        denial = random.choice(["Prior authorization not obtained", "Service not covered",
                                "Duplicate claim"]) if status == "Denied" else None
        cur.execute("""
            INSERT INTO CLAIMS (CLAIM_ID, PATIENT_ID, CLAIM_TYPE, AMOUNT, STATUS, DENIAL_REASON, CLAIM_DATE)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, [f"CL{random.randint(100000, 999999)}", pid,
              random.choice(["Professional", "Institutional", "Pharmacy", "DME"]),
              round(random.uniform(50, 10000), 2), status, denial,
              (datetime.now() - timedelta(days=random.randint(1, 180))).strftime("%Y-%m-%d")])

    # Clinical note
    dx_list = ", ".join([d[1] for d in patient_dx[:3]])
    med_list = "\n".join([f"- {m[0]} {m[1]}" for m in patient_meds])
    note_text = (
        f"PROGRESS NOTE\n\nPatient: {fname} {lname}\n"
        f"SUBJECTIVE: {age} yo {gender.lower()} presents for follow-up of {dx_list}.\n"
        f"Patient reports stable symptoms. Medication compliance is fair.\n\n"
        f"MEDICATIONS:\n{med_list}\n\n"
        f"ASSESSMENT: {patient_dx[0][1]} - stable management\n"
        f"PLAN: Continue current regimen. Follow up in 3 months. Recheck labs."
    )
    cur.execute("""
        INSERT INTO CLINICAL_NOTES (NOTE_ID, PATIENT_ID, ENCOUNTER_ID, NOTE_TYPE, RAW_TEXT, PARSED_JSON)
        VALUES (%s, %s, %s, %s, %s, NULL)
    """, [f"N{random.randint(100000, 999999)}", pid, random.choice(enc_ids), "Progress Note", note_text])

    # Discharge summary (if any inpatient)
    cur.execute("""
        INSERT INTO DISCHARGE_SUMMARIES (SUMMARY_ID, PATIENT_ID, ENCOUNTER_ID, RAW_TEXT, PARSED_JSON)
        VALUES (%s, %s, %s, %s, NULL)
    """, [f"DS{random.randint(100000, 999999)}", pid, random.choice(enc_ids),
          f"DISCHARGE SUMMARY\nPatient: {fname} {lname}\n"
          f"Admitting Diagnosis: {patient_dx[0][1]}\n"
          f"Hospital Course: Managed with {patient_meds[0][0]}. Improved. Discharged stable.\n"
          f"Follow-up: PCP in 2 weeks."])

    # Care gaps are computed by the CARE_GAPS view — no insert needed

    # Regulatory filing
    filing_types = ["Prior Authorization", "Appeal", "Quality Report", "Safety Report"]
    filing_type = random.choice(filing_types)
    filing_text = (
        f"{filing_type.upper()}\nPatient: {fname} {lname}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"REASON: {filing_type} for {patient_dx[0][1]}\n\n"
        f"DETAILS: Patient with {', '.join([d[1] for d in patient_dx])} "
        f"requires {filing_type.lower()} for continued management.\n"
        f"Current medications: {', '.join([m[0] for m in patient_meds])}\n\n"
        f"RECOMMENDATION: Approve {filing_type.lower()} for continued care."
    )
    cur.execute("""
        INSERT INTO REGULATORY_FILINGS (FILING_ID, PATIENT_ID, FILING_TYPE, RAW_TEXT, PARSED_JSON)
        VALUES (%s, %s, %s, %s, NULL)
    """, [f"RF{random.randint(100000, 999999)}", pid, filing_type, filing_text])

    conn.commit()
    if owns_conn:
        conn.close()

    msg = f"Generated: {fname} {lname} (ID: {pid}), Age: {age}, {gender}"
    print(msg)
    return msg


if __name__ == "__main__":
    generate_and_insert()
