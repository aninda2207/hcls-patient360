# HCLS Patient 360 — Hackathon Demo Script (2 Minutes)

## Setup
- App URL: https://hcls-patient360-m74hz3rzqbax3cwlmvdirl.streamlit.app/
- Test patient: Any HIGH risk patient (e.g., P00089 Elizabeth Taylor)
- Have a sample `.txt` or `.pdf` prescription ready on desktop

## Demo Flow

### [0:00-0:30] Dashboard Overview
1. Open app — show the branded dashboard with dark sidebar
2. Point out: "100 synthetic patients, 56 high-risk — here's the risk distribution"
3. Show the donut chart and KPI metric cards
4. Type "Smith" in search — show instant filtering
5. Note the color-coded risk tiers in the registry table

### [0:30-1:00] Patient 360 Deep Dive
1. Click a HIGH risk patient from the table
2. Show the patient header card with demographics + risk at a glance
3. Expand "LACE Score Breakdown" — explain the L-A-C-E components
4. Show care gaps with severity colors and evidence sources
5. Click through tabs: Encounters chart, Medication adherence bars, Lab trends, Claims donut
6. Scroll to "Similar Patients" — show risk-matched cohort

### [1:00-1:30] Clinical Q&A
1. Go to Clinical Q&A page
2. Select the same patient
3. Click "What are this patient's active diagnoses?"
4. Show the cited answer with document references
5. Expand "Source Documents" — show confidence badges (High/Medium/Low)
6. Ask a custom question: "Has the patient had any emergency visits?"

### [1:30-2:00] Document Upload + Audit Trail
1. Go to Upload Document page
2. Upload a sample prescription text file
3. Click "Parse & Extract Data" — show keyword extraction results
4. Go to Audit Log page — show all actions logged with timestamps
5. "Every action is tracked for HIPAA compliance"

### [2:00-2:30] Manual Patient Creation (BONUS)
1. Go to "Add New Patient" page
2. Fill in: Name, DOB, Gender
3. Add an encounter (Outpatient, Primary Care)
4. Add 2-3 diagnoses from ICD-10 dropdown, linked to the encounter
5. Add 2-3 medications with dosages
6. Add 1-2 lab results — note the auto-filled units and abnormal flags
7. Click "Save Patient" — patient is inserted into all tables
8. "Now let's view them in Patient 360..." — switch and search for the new ID

## Key Talking Points
- "Every answer traces back to a source document — never opaque"
- "Risk scores are fully explainable — click to see the breakdown"
- "Upload any clinical document and it becomes searchable in seconds"
- "Full audit trail for compliance — every view, query, and upload is logged"
- "Built on Snowflake with Cortex AI-powered document parsing"

## Backup Plans
- If upload fails: show the pre-loaded clinical notes instead
- If chart doesn't load: refresh the page
- If patient not found: use patient ID P00089 (Elizabeth Taylor, HIGH risk)
- If connection drops: the app will reconnect on next page load

- ## Demo Video

[Watch HCLS Patient 360 Demo on YouTube](https://youtu.be/n6w0bc_731A)
