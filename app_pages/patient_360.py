import csv
import io
import json

import altair as alt
import pandas as pd
import streamlit as st

from src.data_loader import (
    get_all_patients, get_patient_detail, get_patient_encounters,
    get_patient_care_gaps, get_patient_medications, get_patient_labs, get_patient_claims,
    log_audit_event, run_query,
)
from src.risk_scoring import explain_charlson, explain_lace, get_risk_summary
from src.ui import SEVERITY_COLORS, TIER_COLORS, badge, page_header, patient_options as build_options

patients = get_all_patients()
patient_options = build_options(patients)

page_header("Patient 360", "Unified clinical, risk and claims view for a single patient.", icon="person")

selected_label = st.selectbox("Select a patient", options=list(patient_options.keys()))
if not selected_label:
    st.stop()

patient_id = patient_options[selected_label]
patient = get_patient_detail(patient_id)
if patient is None:
    st.error("Patient not found.")
    st.stop()

log_audit_event("VIEW_PATIENT", patient_id=patient_id, details={"page": "patient_360"})

risk_tier = patient.get("risk_tier", "LOW")

# Export payloads (unchanged content)
summary_data = {
    "Patient ID": patient_id,
    "Name": f"{patient['first_name']} {patient['last_name']}",
    "Age": patient.get("age"),
    "Gender": patient.get("gender"),
    "Risk Tier": risk_tier,
    "LACE Score": patient.get("lace_score"),
    "Charlson Index": patient.get("charlson_index"),
}
csv_buffer = io.StringIO()
writer = csv.DictWriter(csv_buffer, fieldnames=summary_data.keys())
writer.writeheader()
writer.writerow(summary_data)
export_json = {
    "demographics": {
        "patient_id": patient_id,
        "first_name": patient["first_name"],
        "last_name": patient["last_name"],
        "age": patient.get("age"),
        "gender": patient.get("gender"),
        "ethnicity": patient.get("ethnicity"),
        "region": patient.get("region"),
        "insurance_type": patient.get("insurance_type"),
    },
    "risk": {"risk_tier": risk_tier, "lace_score": patient.get("lace_score"),
             "charlson_index": patient.get("charlson_index")},
}

# Patient header card
with st.container(border=True):
    left, right = st.columns([3, 2], vertical_alignment="center")
    with left:
        st.markdown(f"### {patient['first_name']} {patient['last_name']}")
        details = " · ".join(str(v) for v in [
            patient.get("ethnicity"), patient.get("region"), patient.get("insurance_type")
        ] if v)
        st.markdown(f"{badge(risk_tier, TIER_COLORS, icon='monitor_heart')} &nbsp; `{patient_id}` &nbsp; {details}")
    with right:
        m1, m2, m3, m4, m5 = st.columns([1, 1, 1, 1, 1.2], vertical_alignment="center")
        m1.metric("Age", patient.get("age"))
        m2.metric("Gender", patient.get("gender"))
        m3.metric("LACE", patient.get("lace_score"))
        m4.metric("Charlson", patient.get("charlson_index"))
        with m5.popover("Export", icon=":material/download:", width="stretch"):
            st.download_button(":material/table: Download CSV", csv_buffer.getvalue(),
                               f"patient_{patient_id}_summary.csv", "text/csv", width="stretch")
            st.download_button(":material/data_object: Download JSON",
                               json.dumps(export_json, indent=2, default=str),
                               f"patient_{patient_id}_summary.json", "application/json", width="stretch")

# Risk assessment
st.markdown("#### Risk Assessment")
risk_summary = get_risk_summary(patient)
if risk_tier == "HIGH":
    st.error(risk_summary, icon=":material/priority_high:")
elif risk_tier == "MEDIUM":
    st.warning(risk_summary, icon=":material/warning:")
else:
    st.success(risk_summary, icon=":material/check_circle:")

x1, x2 = st.columns(2)
with x1.expander(f"LACE score breakdown · {patient.get('lace_score', 0)}", icon=":material/stacked_bar_chart:"):
    lace_components = explain_lace(
        patient.get("lace_score", 0),
        patient.get("charlson_index", 0),
        patient,
    )
    for comp in lace_components:
        st.markdown(f"- **{comp['component']}**: {comp['score']} — {comp['detail']}")

with x2.expander(f"Charlson contributing factors · {patient.get('charlson_index', 0)}", icon=":material/list_alt:"):
    active_dx = patient.get("active_diagnoses")
    factors = explain_charlson(active_dx)
    if factors:
        for f in factors:
            st.markdown(f"- **{f['condition']}** ({f['icd10']}) — weight {f['weight']}")
    else:
        st.info("No Charlson-weighted conditions found in active diagnoses.")

# Care gaps
gaps_df = get_patient_care_gaps(patient_id)
st.markdown(f"#### Care Gaps {badge(len(gaps_df), {}) if not gaps_df.empty else ''}")
if gaps_df.empty:
    st.success("No open care gaps for this patient.", icon=":material/verified:")
else:
    for _, gap in gaps_df.iterrows():
        with st.container(border=True):
            gc1, gc2 = st.columns([3, 2])
            gc1.markdown(f"{badge(gap['severity'], SEVERITY_COLORS)} **{gap['gap_type']}**")
            gc1.markdown(gap["gap_description"])
            gc2.markdown(f":material/assignment_turned_in: **Action:** {gap['recommended_action']}")
            gc2.caption(f"Evidence: {gap['evidence_source']}")

# Tabs for detailed clinical data
st.markdown("#### Clinical Record")
tab_enc, tab_meds, tab_labs, tab_claims = st.tabs(
    [":material/calendar_month: Encounters", ":material/medication: Medications",
     ":material/labs: Lab Results", ":material/receipt_long: Claims"]
)

with tab_enc:
    enc_df = get_patient_encounters(patient_id)
    if enc_df.empty:
        st.info("No encounters found.")
    else:
        st.dataframe(enc_df, width="stretch", hide_index=True)
        chart_data = enc_df.copy()
        chart_data["encounter_date"] = pd.to_datetime(chart_data["encounter_date"])
        type_counts = chart_data.groupby("encounter_type").size().reset_index(name="count")
        chart = alt.Chart(type_counts).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#0B5FFF").encode(
            x=alt.X("encounter_type:N", title="Type", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("count:Q", title="Count"),
        ).properties(height=250)
        st.altair_chart(chart, width="stretch")

with tab_meds:
    meds_df = get_patient_medications(patient_id)
    if meds_df.empty:
        st.info("No medications found.")
    else:
        st.dataframe(meds_df, width="stretch", hide_index=True)
        active = meds_df[meds_df["end_date"].isna()]
        if not active.empty:
            adh_chart = alt.Chart(active).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("drug_name:N", title="Medication", sort="-y"),
                y=alt.Y("adherence:Q", title="Adherence", scale=alt.Scale(domain=[0, 1])),
                color=alt.condition(
                    alt.datum.adherence < 0.8,
                    alt.value("#DC2626"),
                    alt.value("#059669"),
                ),
            ).properties(height=250, title="Active Medication Adherence")
            st.altair_chart(adh_chart, width="stretch")

with tab_labs:
    labs_df = get_patient_labs(patient_id)
    if labs_df.empty:
        st.info("No lab results found.")
    else:
        test_filter = st.multiselect("Filter by test", labs_df["test_name"].unique().tolist(),
                                     default=labs_df["test_name"].unique().tolist()[:3])
        filtered_labs = labs_df[labs_df["test_name"].isin(test_filter)] if test_filter else labs_df
        st.dataframe(filtered_labs, width="stretch", hide_index=True)

        if not filtered_labs.empty:
            fl = filtered_labs.copy()
            fl["lab_date"] = pd.to_datetime(fl["lab_date"])
            lab_chart = alt.Chart(fl).mark_line(point=True).encode(
                x=alt.X("lab_date:T", title="Date"),
                y=alt.Y("result_value:Q", title="Value"),
                color="test_name:N",
                tooltip=["test_name", "result_value", "unit", "lab_date"],
            ).properties(height=300)
            st.altair_chart(lab_chart, width="stretch")

with tab_claims:
    claims_df = get_patient_claims(patient_id)
    if claims_df.empty:
        st.info("No claims found.")
    else:
        st.dataframe(claims_df, width="stretch", hide_index=True)
        status_counts = claims_df.groupby("status").size().reset_index(name="count")
        claim_chart = alt.Chart(status_counts).mark_arc(innerRadius=50).encode(
            theta="count:Q",
            color="status:N",
        ).properties(height=250, title="Claims by Status")
        st.altair_chart(claim_chart, width="stretch")

# Similar patients
st.markdown("#### Similar Patients")
st.caption("Patients with similar risk profiles and diagnoses")
similar = run_query("""
    SELECT PATIENT_ID, FIRST_NAME, LAST_NAME, AGE, GENDER, RISK_TIER,
           LACE_SCORE, CHARLSON_INDEX
    FROM PATIENT_360_VIEW
    WHERE PATIENT_ID != %s
    ORDER BY ABS(LACE_SCORE - %s) + ABS(CHARLSON_INDEX - %s)
    LIMIT 5
""", [patient_id, patient.get("lace_score", 0), patient.get("charlson_index", 0)])
if not similar.empty:
    st.dataframe(similar, width="stretch", hide_index=True)
else:
    st.info("No similar patients found.")
