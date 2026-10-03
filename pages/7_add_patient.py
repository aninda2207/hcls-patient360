import streamlit as st
import json
import os
import random
from datetime import datetime

st.set_page_config(page_title="Add New Patient", page_icon=":material/person_add:", layout="wide")

css_path = os.path.join(os.path.dirname(__file__), "..", "static", "styles.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from src.data_loader import get_connection, log_audit_event, _bind


def _exec(cur, sql, params):
    sql, params = _bind(sql, params)
    cur.execute(sql, params)

st.markdown("## :material/person_add: Add New Patient")
st.caption("Enter patient details manually. All fields marked with * are required.")

# ============================================================
# SECTION 1: Demographics
# ============================================================
st.markdown("### Demographics")

with st.container(border=True):
    d1, d2, d3 = st.columns(3)
    with d1:
        first_name = st.text_input("First Name *", placeholder="e.g., John", key="first_name")
    with d2:
        last_name = st.text_input("Last Name *", placeholder="e.g., Smith", key="last_name")
    with d3:
        date_of_birth = st.date_input("Date of Birth *", key="dob")

    d4, d5, d6, d7 = st.columns(4)
    with d4:
        gender = st.selectbox("Gender *", ["", "Male", "Female", "Other"], key="gender")
    with d5:
        ethnicity = st.selectbox("Ethnicity", ["", "Caucasian", "African American", "Hispanic",
                                                "Asian", "Native American", "Other"], key="ethnicity")
    with d6:
        region = st.selectbox("Region", ["", "Northeast", "Southeast", "Midwest",
                                          "Southwest", "West"], key="region")
    with d7:
        insurance_type = st.selectbox("Insurance Type", ["", "Medicare", "Medicaid",
                                                         "Commercial", "Self-Pay", "VA"], key="insurance")

    if date_of_birth:
        today = datetime.now().date()
        age = today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
        st.caption(f"Calculated Age: {age} years")
    else:
        age = None

# ============================================================
# SECTION 2: Encounters
# ============================================================
st.markdown("### Encounters")

with st.container(border=True):
    st.caption("Add recent encounters for this patient. Diagnoses are linked to encounters.")

    if "encounters" not in st.session_state:
        st.session_state.encounters = []

    col_e1, col_e2, col_e3, col_e4, col_e5 = st.columns([2, 2, 2, 1, 1])
    with col_e1:
        enc_type = st.selectbox("Encounter Type", ["", "Emergency", "Inpatient", "Outpatient",
                                                     "Observation", "Telehealth"], key="enc_type")
    with col_e2:
        enc_date = st.date_input("Encounter Date", key="enc_date")
    with col_e3:
        enc_dept = st.selectbox("Department", ["", "Primary Care", "Cardiology", "Emergency",
                                                "Surgery", "Oncology", "Radiology", "Pulmonology",
                                                "Nephrology", "Endocrinology", "Neurology"], key="enc_dept")
    with col_e4:
        enc_los = st.number_input("Length of Stay (days)", value=0, min_value=0, key="enc_los")
    with col_e5:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(":material/add: Add", key="add_enc", use_container_width=True):
            if enc_type and enc_dept:
                st.session_state.encounters.append({
                    "encounter_id": f"E{random.randint(100000, 999999)}",
                    "encounter_type": enc_type,
                    "encounter_date": enc_date,
                    "department": enc_dept,
                    "length_of_stay": enc_los,
                })
                st.rerun()

    if st.session_state.encounters:
        st.markdown("**Added Encounters:**")
        for i, enc in enumerate(st.session_state.encounters):
            c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1, 1])
            c1.markdown(enc["encounter_type"])
            c2.markdown(str(enc["encounter_date"]))
            c3.markdown(enc["department"])
            c4.markdown(f"{enc['length_of_stay']} days")
            if c5.button(":material/delete:", key=f"del_enc_{i}"):
                st.session_state.encounters.pop(i)
                st.rerun()

# ============================================================
# SECTION 3: Diagnoses
# ============================================================
st.markdown("### Diagnoses")

with st.container(border=True):
    st.caption("Add all active diagnoses. Each diagnosis is linked to an encounter.")

    icd10_options = [
        ("E11.9", "Type 2 diabetes mellitus without complications"),
        ("I25.10", "Atherosclerotic heart disease"),
        ("I50.9", "Heart failure, unspecified"),
        ("I48.0", "Paroxysmal atrial fibrillation"),
        ("N18.3", "Chronic kidney disease, stage 3"),
        ("J44.1", "COPD with acute exacerbation"),
        ("J45.20", "Mild intermittent asthma"),
        ("C34.90", "Malignant neoplasm of lung"),
        ("I10", "Essential hypertension"),
        ("F32.1", "Major depressive disorder"),
        ("E66.01", "Morbid obesity"),
        ("E78.5", "Hyperlipidemia"),
        ("E03.9", "Hypothyroidism"),
        ("G20", "Parkinson disease"),
        ("N18.6", "End stage renal disease"),
        ("I21.9", "Acute myocardial infarction"),
        ("J96.01", "Acute respiratory failure"),
    ]

    if "diagnoses" not in st.session_state:
        st.session_state.diagnoses = []

    enc_labels = [f"{e['encounter_id']} — {e['encounter_type']} ({e['encounter_date']})"
                  for e in st.session_state.encounters]

    col_dx1, col_dx2, col_dx3, col_dx4, col_dx5 = st.columns([3, 2, 2, 2, 1])
    with col_dx1:
        dx_code = st.selectbox("ICD-10 Code", [""] + [f"{code} — {desc}" for code, desc in icd10_options], key="dx_code")
    with col_dx2:
        dx_severity = st.selectbox("Severity", ["", "Mild", "Moderate", "Severe"], key="dx_severity")
    with col_dx3:
        dx_encounter = st.selectbox("Linked Encounter", [""] + enc_labels, key="dx_encounter")
    with col_dx4:
        dx_description = st.text_input("Description (optional)", placeholder="Custom description", key="dx_desc")
    with col_dx5:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(":material/add: Add", key="add_dx", use_container_width=True):
            if dx_code and dx_severity:
                code = dx_code.split(" — ")[0]
                desc = dx_description or (dx_code.split(" — ")[1] if " — " in dx_code else dx_code)
                enc_id = dx_encounter.split(" — ")[0] if dx_encounter else None
                st.session_state.diagnoses.append({
                    "code": code,
                    "description": desc,
                    "severity": dx_severity,
                    "encounter_id": enc_id,
                })
                st.rerun()

    if not st.session_state.encounters:
        st.info("Add at least one encounter above so diagnoses can be linked to it.")

    if st.session_state.diagnoses:
        st.markdown("**Added Diagnoses:**")
        for i, dx in enumerate(st.session_state.diagnoses):
            c1, c2, c3, c4, c5 = st.columns([2, 3, 1, 2, 1])
            c1.markdown(f"`{dx['code']}`")
            c2.markdown(dx["description"])
            c3.markdown(dx["severity"])
            c4.markdown(f"Enc: {dx['encounter_id'] or 'N/A'}")
            if c5.button(":material/delete:", key=f"del_dx_{i}"):
                st.session_state.diagnoses.pop(i)
                st.rerun()

# ============================================================
# SECTION 4: Medications
# ============================================================
st.markdown("### Medications")

with st.container(border=True):
    st.caption("Add all current medications for this patient")

    if "medications" not in st.session_state:
        st.session_state.medications = []

    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns([2, 2, 2, 1, 1])
    with col_m1:
        med_name = st.text_input("Drug Name *", placeholder="e.g., Metformin", key="med_name")
    with col_m2:
        med_dosage = st.text_input("Dosage *", placeholder="e.g., 500mg BID", key="med_dosage")
    with col_m3:
        med_start = st.date_input("Start Date", key="med_start")
    with col_m4:
        med_active = st.checkbox("Active", value=True, key="med_active")
    with col_m5:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(":material/add: Add", key="add_med", use_container_width=True):
            if med_name and med_dosage:
                st.session_state.medications.append({
                    "drug_name": med_name,
                    "dosage": med_dosage,
                    "start_date": med_start,
                    "end_date": None if med_active else datetime.now().date(),
                    "adherence": 1.0,
                })
                st.rerun()

    if st.session_state.medications:
        st.markdown("**Added Medications:**")
        for i, med in enumerate(st.session_state.medications):
            c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1, 1])
            c1.markdown(med["drug_name"])
            c2.markdown(med["dosage"])
            c3.markdown(f"Started: {med['start_date']}")
            c4.markdown("Active" if med["end_date"] is None else "Stopped")
            if c5.button(":material/delete:", key=f"del_med_{i}"):
                st.session_state.medications.pop(i)
                st.rerun()

# ============================================================
# SECTION 5: Lab Results
# ============================================================
st.markdown("### Lab Results")

with st.container(border=True):
    st.caption("Add recent lab results for this patient")

    if "labs" not in st.session_state:
        st.session_state.labs = []

    lab_options = [
        ("HbA1c", "%", "4.0-5.6"),
        ("LDL Cholesterol", "mg/dL", "<100"),
        ("Creatinine", "mg/dL", "0.7-1.3"),
        ("eGFR", "mL/min", ">60"),
        ("TSH", "mIU/L", "0.4-4.0"),
        ("WBC", "K/uL", "4.5-11.0"),
        ("Hemoglobin", "g/dL", "12.0-17.5"),
        ("Blood Glucose", "mg/dL", "70-100"),
        ("BNP", "pg/mL", "<100"),
        ("Potassium", "mEq/L", "3.5-5.0"),
        ("Sodium", "mEq/L", "136-145"),
        ("Total Cholesterol", "mg/dL", "<200"),
    ]
    lab_lookup = {name: (unit, ref) for name, unit, ref in lab_options}

    col_l1, col_l2, col_l3, col_l4, col_l5 = st.columns([2, 1, 1, 1, 1])
    with col_l1:
        lab_test = st.selectbox("Test Name", [""] + [l[0] for l in lab_options], key="lab_test")
    with col_l2:
        lab_value = st.number_input("Result Value", value=0.0, step=0.1, key="lab_value")
    with col_l3:
        default_unit = lab_lookup[lab_test][0] if lab_test in lab_lookup else ""
        lab_unit = st.text_input("Unit", value=default_unit, key="lab_unit")
    with col_l4:
        lab_date = st.date_input("Lab Date", key="lab_date")
    with col_l5:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(":material/add: Add", key="add_lab", use_container_width=True):
            if lab_test and lab_value:
                ref = lab_lookup.get(lab_test, ("", ""))[1]
                abnormal = None
                if ref and "-" in ref:
                    parts = ref.split("-")
                    try:
                        rlo, rhi = float(parts[0]), float(parts[1])
                        if lab_value > rhi:
                            abnormal = "H"
                        elif lab_value < rlo:
                            abnormal = "L"
                    except ValueError:
                        pass
                elif ref and ref.startswith("<"):
                    try:
                        if lab_value > float(ref[1:]):
                            abnormal = "H"
                    except ValueError:
                        pass
                elif ref and ref.startswith(">"):
                    try:
                        if lab_value < float(ref[1:]):
                            abnormal = "L"
                    except ValueError:
                        pass

                st.session_state.labs.append({
                    "test_name": lab_test,
                    "result_value": lab_value,
                    "unit": lab_unit or default_unit,
                    "reference_range": ref,
                    "lab_date": lab_date,
                    "abnormal_flag": abnormal,
                })
                st.rerun()

    if st.session_state.labs:
        st.markdown("**Added Lab Results:**")
        for i, lab in enumerate(st.session_state.labs):
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 2, 1])
            c1.markdown(lab["test_name"])
            c2.markdown(f"{lab['result_value']} {lab['unit']}")
            c3.markdown(f"Ref: {lab['reference_range']}")
            flag = lab["abnormal_flag"]
            c4.markdown(f"**{'HIGH' if flag == 'H' else 'LOW'}**" if flag else "Normal")
            if c5.button(":material/delete:", key=f"del_lab_{i}"):
                st.session_state.labs.pop(i)
                st.rerun()

# ============================================================
# SECTION 6: Claims
# ============================================================
st.markdown("### Claims")

with st.container(border=True):
    st.caption("Add insurance claims for this patient")

    if "claims" not in st.session_state:
        st.session_state.claims = []

    col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns([2, 1, 1, 2, 1])
    with col_c1:
        claim_type = st.selectbox("Claim Type", ["", "Professional", "Institutional",
                                                   "Pharmacy", "DME"], key="claim_type")
    with col_c2:
        claim_amount = st.number_input("Amount ($)", value=0.0, step=0.01, key="claim_amount")
    with col_c3:
        claim_status = st.selectbox("Status", ["", "Paid", "Pending", "Denied"], key="claim_status")
    with col_c4:
        claim_date = st.date_input("Claim Date", key="claim_date")
    with col_c5:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(":material/add: Add", key="add_claim", use_container_width=True):
            if claim_type and claim_status:
                st.session_state.claims.append({
                    "claim_type": claim_type,
                    "amount": claim_amount,
                    "status": claim_status,
                    "claim_date": claim_date,
                })
                st.rerun()

    if claim_status == "Denied":
        claim_denial = st.text_input("Denial Reason", placeholder="e.g., Prior authorization not obtained", key="claim_denial")
    else:
        claim_denial = None

    if st.session_state.claims:
        st.markdown("**Added Claims:**")
        for i, claim in enumerate(st.session_state.claims):
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 2, 1])
            c1.markdown(claim["claim_type"])
            c2.markdown(f"${claim['amount']:.2f}")
            c3.markdown(claim["status"])
            c4.markdown(str(claim["claim_date"]))
            if c5.button(":material/delete:", key=f"del_claim_{i}"):
                st.session_state.claims.pop(i)
                st.rerun()

# ============================================================
# SECTION 7: Clinical Notes
# ============================================================
st.markdown("### Clinical Notes")

with st.container(border=True):
    st.caption("Add clinical notes for this patient")

    if "notes" not in st.session_state:
        st.session_state.notes = []

    col_n1, col_n2 = st.columns([2, 3])
    with col_n1:
        note_type = st.selectbox("Note Type", ["", "Progress Note", "H&P", "Consult Note",
                                                "Nursing Note", "Discharge Note", "Prescription"], key="note_type")
    with col_n2:
        note_text = st.text_area("Note Content", height=100,
                                  placeholder="Enter clinical note text here...", key="note_text")

    if st.button(":material/add: Add Note", key="add_note", use_container_width=True):
        if note_type and note_text:
            st.session_state.notes.append({
                "note_type": note_type,
                "raw_text": note_text,
            })
            st.rerun()

    if st.session_state.notes:
        st.markdown("**Added Notes:**")
        for i, note in enumerate(st.session_state.notes):
            c1, c2, c3 = st.columns([2, 3, 1])
            c1.markdown(note["note_type"])
            c2.markdown(note["raw_text"][:100] + "..." if len(note["raw_text"]) > 100 else note["raw_text"])
            if c3.button(":material/delete:", key=f"del_note_{i}"):
                st.session_state.notes.pop(i)
                st.rerun()

# ============================================================
# SUBMIT
# ============================================================
st.divider()

errors = []
if not first_name:
    errors.append("First Name is required")
if not last_name:
    errors.append("Last Name is required")
if not date_of_birth:
    errors.append("Date of Birth is required")
if not gender:
    errors.append("Gender is required")
if not st.session_state.get("encounters"):
    errors.append("At least one encounter is required")
if not st.session_state.get("diagnoses"):
    errors.append("At least one diagnosis is required")

if errors:
    st.warning("Please fix the following before submitting:")
    for err in errors:
        st.markdown(f"- {err}")

with st.expander("Review All Entered Data", expanded=False):
    st.markdown(f"**Name:** {first_name} {last_name}")
    st.markdown(f"**DOB:** {date_of_birth} (Age: {age})")
    st.markdown(f"**Gender:** {gender}")
    st.markdown(f"**Ethnicity:** {ethnicity or 'Not specified'}")
    st.markdown(f"**Region:** {region or 'Not specified'}")
    st.markdown(f"**Insurance:** {insurance_type or 'Not specified'}")
    st.markdown(f"**Encounters:** {len(st.session_state.get('encounters', []))}")
    st.markdown(f"**Diagnoses:** {len(st.session_state.get('diagnoses', []))}")
    st.markdown(f"**Medications:** {len(st.session_state.get('medications', []))}")
    st.markdown(f"**Lab Results:** {len(st.session_state.get('labs', []))}")
    st.markdown(f"**Claims:** {len(st.session_state.get('claims', []))}")
    st.markdown(f"**Clinical Notes:** {len(st.session_state.get('notes', []))}")

col_save, col_clear = st.columns(2)

with col_save:
    if st.button(":material/save: Save Patient", type="primary", use_container_width=True):
        if errors:
            st.error("Please fix all errors before saving.")
        else:
            with st.spinner("Saving patient to database..."):
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("USE DATABASE HCLS_PATIENT360")
                    cur.execute("USE SCHEMA PUBLIC")

                    patient_id = f"P{random.randint(10000, 99999)}"

                    _exec(cur, """
                        INSERT INTO PATIENTS (PATIENT_ID, FIRST_NAME, LAST_NAME, AGE, GENDER,
                                              ETHNICITY, REGION, INSURANCE_TYPE)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, [patient_id, first_name, last_name, age, gender,
                          ethnicity or None, region or None, insurance_type or None])

                    enc_id_list = []
                    for enc in st.session_state.encounters:
                        eid = enc["encounter_id"]
                        enc_id_list.append(eid)
                        _exec(cur, """
                            INSERT INTO ENCOUNTERS (ENCOUNTER_ID, PATIENT_ID, ENCOUNTER_DATE,
                                                     ENCOUNTER_TYPE, DEPARTMENT, LENGTH_OF_STAY)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, [eid, patient_id,
                              enc["encounter_date"], enc["encounter_type"],
                              enc["department"], enc["length_of_stay"]])

                    for dx in st.session_state.diagnoses:
                        enc_id = dx.get("encounter_id") or (enc_id_list[0] if enc_id_list else None)
                        _exec(cur, """
                            INSERT INTO DIAGNOSES (DIAGNOSIS_ID, ENCOUNTER_ID, ICD10_CODE,
                                                   DESCRIPTION, SEVERITY)
                            VALUES (%s, %s, %s, %s, %s)
                        """, [f"D{random.randint(100000, 999999)}", enc_id,
                              dx["code"], dx["description"], dx["severity"]])

                    for med in st.session_state.medications:
                        _exec(cur, """
                            INSERT INTO MEDICATIONS (MEDICATION_ID, PATIENT_ID, DRUG_NAME,
                                                      DOSAGE, START_DATE, END_DATE, ADHERENCE)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, [f"M{random.randint(100000, 999999)}", patient_id,
                              med["drug_name"], med["dosage"],
                              med["start_date"], med["end_date"], med["adherence"]])

                    for lab in st.session_state.labs:
                        _exec(cur, """
                            INSERT INTO LAB_RESULTS (LAB_ID, PATIENT_ID, TEST_NAME,
                                                      RESULT_VALUE, UNIT, REFERENCE_RANGE,
                                                      LAB_DATE, ABNORMAL_FLAG)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, [f"L{random.randint(100000, 999999)}", patient_id,
                              lab["test_name"], lab["result_value"], lab["unit"],
                              lab["reference_range"], lab["lab_date"], lab["abnormal_flag"]])

                    for claim in st.session_state.claims:
                        _exec(cur, """
                            INSERT INTO CLAIMS (CLAIM_ID, PATIENT_ID, CLAIM_TYPE, AMOUNT,
                                                STATUS, DENIAL_REASON, CLAIM_DATE)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, [f"CL{random.randint(100000, 999999)}", patient_id,
                              claim["claim_type"], claim["amount"], claim["status"],
                              claim.get("denial_reason"), claim["claim_date"]])

                    for note in st.session_state.notes:
                        _exec(cur, """
                            INSERT INTO CLINICAL_NOTES (NOTE_ID, PATIENT_ID, ENCOUNTER_ID,
                                                         NOTE_TYPE, RAW_TEXT, PARSED_JSON)
                            VALUES (%s, %s, %s, %s, %s, NULL)
                        """, [f"N{random.randint(100000, 999999)}", patient_id,
                              enc_id_list[0] if enc_id_list else None,
                              note["note_type"], note["raw_text"]])

                    conn.commit()

                    log_audit_event("ADD_PATIENT", patient_id=patient_id,
                                   details={"source": "manual_form", "name": f"{first_name} {last_name}"})

                    st.success(f"Patient saved successfully! Patient ID: `{patient_id}`")
                    st.balloons()

                    st.session_state.diagnoses = []
                    st.session_state.medications = []
                    st.session_state.labs = []
                    st.session_state.encounters = []
                    st.session_state.claims = []
                    st.session_state.notes = []

                    st.markdown("### Next Steps")
                    st.markdown(f"- View patient in **Patient 360** page (search for `{patient_id}`)")
                    st.markdown("- Ask questions in **Clinical Q&A** page")
                    st.markdown("- Generate care actions in **Care Actions** page")

                except Exception as e:
                    st.error(f"Error saving patient: {e}")
                    import traceback
                    st.code(traceback.format_exc())

with col_clear:
    if st.button(":material/refresh: Clear Form", use_container_width=True):
        for key in ["diagnoses", "medications", "labs", "encounters", "claims", "notes"]:
            st.session_state[key] = []
        st.rerun()
