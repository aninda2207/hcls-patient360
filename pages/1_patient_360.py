import streamlit as st
import pathlib
import altair as alt
import pandas as pd
import json
import csv
import io

st.set_page_config(page_title="Patient 360", page_icon=":material/person:", layout="wide")

css_path = pathlib.Path(__file__).parent.parent / "static" / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from src.data_loader import (
    get_all_patients, get_patient_detail, get_patient_encounters,
    get_patient_care_gaps, get_patient_medications, get_patient_labs, get_patient_claims,
    log_audit_event, run_query,
)
from src.risk_scoring import explain_charlson, explain_lace, get_risk_summary

patients = get_all_patients()
patient_options = {
    f"{r['patient_id']} — {r['first_name']} {r['last_name']} ({r['risk_tier']})": r["patient_id"]
    for _, r in patients.iterrows()
}

st.markdown("## :material/person: Patient 360 Dashboard")

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

# Patient header card
with st.container(border=True):
    pc1, pc2, pc3, pc4, pc5, pc6 = st.columns([2, 1, 1, 1, 1, 1])
    pc1.markdown(f"### :material/person: {patient['first_name']} {patient['last_name']}")
    pc1.caption(f"ID: `{patient_id}` | {patient.get('ethnicity', '')} | {patient.get('region', '')} | {patient.get('insurance_type', '')}")
    pc2.metric("Age", patient.get("age"))
    pc3.metric("Gender", patient.get("gender"))
    pc4.metric("Risk Tier", risk_tier)
    pc5.metric("LACE", patient.get("lace_score"))
    pc6.metric("Charlson", patient.get("charlson_index"))

# Export patient summary
with st.expander("Export Patient Summary"):
    col_csv, col_json = st.columns(2)
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
    col_csv.download_button("Download CSV", csv_buffer.getvalue(),
                             f"patient_{patient_id}_summary.csv", "text/csv")
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
    col_json.download_button("Download JSON", json.dumps(export_json, indent=2, default=str),
                              f"patient_{patient_id}_summary.json", "application/json")

st.divider()

# Risk scores
st.markdown("### Risk Assessment")
r1, r2, r3 = st.columns(3)
tier_color = {"HIGH": "#DC2626", "MEDIUM": "#D97706", "LOW": "#059669"}.get(risk_tier, "#6B7280")
r1.markdown(f"<div style='text-align:center;padding:12px;border-radius:8px;border:2px solid {tier_color};'>"
            f"<span style='font-size:28px;font-weight:700;color:{tier_color};'>{risk_tier}</span><br>"
            f"<span style='font-size:12px;color:#64748B;'>Risk Tier</span></div>", unsafe_allow_html=True)
r2.metric("LACE Score", patient.get("lace_score", 0))
r3.metric("Charlson Index", patient.get("charlson_index", 0))

with st.expander("LACE Score Breakdown", expanded=False):
    lace_components = explain_lace(
        patient.get("lace_score", 0),
        patient.get("charlson_index", 0),
        patient,
    )
    for comp in lace_components:
        st.markdown(f"- **{comp['component']}**: {comp['score']} — {comp['detail']}")

with st.expander("Charlson Contributing Factors", expanded=False):
    active_dx = patient.get("active_diagnoses")
    factors = explain_charlson(active_dx)
    if factors:
        for f in factors:
            st.markdown(f"- **{f['condition']}** ({f['icd10']}) — weight {f['weight']}")
    else:
        st.info("No Charlson-weighted conditions found in active diagnoses.")

st.divider()

# Care Gaps
st.markdown("### Care Gaps")
gaps_df = get_patient_care_gaps(patient_id)
if gaps_df.empty:
    st.success("No open care gaps for this patient.")
else:
    for _, gap in gaps_df.iterrows():
        sev = gap["severity"]
        sev_color = {"High": "#DC2626", "Medium": "#D97706", "Low": "#059669"}.get(sev, "#6B7280")
        with st.container(border=True):
            gc1, gc2 = st.columns([3, 1])
            gc1.markdown(f"<span style='color:{sev_color};font-weight:700;'>{sev}</span> **{gap['gap_type']}**: {gap['gap_description']}", unsafe_allow_html=True)
            gc2.markdown(f"**Action:** {gap['recommended_action']}")
            st.caption(f"Evidence: {gap['evidence_source']}")

st.divider()

# Tabs for detailed clinical data
tab_enc, tab_meds, tab_labs, tab_claims = st.tabs(
    [":material/calendar_month: Encounters", ":material/medication: Medications",
     ":material/labs: Lab Results", ":material/receipt_long: Claims"]
)

with tab_enc:
    enc_df = get_patient_encounters(patient_id)
    if enc_df.empty:
        st.info("No encounters found.")
    else:
        st.dataframe(enc_df, use_container_width=True, hide_index=True)
        chart_data = enc_df.copy()
        chart_data["encounter_date"] = pd.to_datetime(chart_data["encounter_date"])
        type_counts = chart_data.groupby("encounter_type").size().reset_index(name="count")
        chart = alt.Chart(type_counts).mark_bar().encode(
            x=alt.X("encounter_type:N", title="Type"),
            y=alt.Y("count:Q", title="Count"),
            color="encounter_type:N",
        ).properties(height=250)
        st.altair_chart(chart, use_container_width=True)

with tab_meds:
    meds_df = get_patient_medications(patient_id)
    if meds_df.empty:
        st.info("No medications found.")
    else:
        st.dataframe(meds_df, use_container_width=True, hide_index=True)
        active = meds_df[meds_df["end_date"].isna()]
        if not active.empty:
            adh_chart = alt.Chart(active).mark_bar().encode(
                x=alt.X("drug_name:N", title="Medication", sort="-y"),
                y=alt.Y("adherence:Q", title="Adherence", scale=alt.Scale(domain=[0, 1])),
                color=alt.condition(
                    alt.datum.adherence < 0.8,
                    alt.value("#DC2626"),
                    alt.value("#059669"),
                ),
            ).properties(height=250, title="Active Medication Adherence")
            st.altair_chart(adh_chart, use_container_width=True)

with tab_labs:
    labs_df = get_patient_labs(patient_id)
    if labs_df.empty:
        st.info("No lab results found.")
    else:
        test_filter = st.multiselect("Filter by test", labs_df["test_name"].unique().tolist(),
                                      default=labs_df["test_name"].unique().tolist()[:3])
        filtered_labs = labs_df[labs_df["test_name"].isin(test_filter)] if test_filter else labs_df
        st.dataframe(filtered_labs, use_container_width=True, hide_index=True)

        if not filtered_labs.empty:
            fl = filtered_labs.copy()
            fl["lab_date"] = pd.to_datetime(fl["lab_date"])
            lab_chart = alt.Chart(fl).mark_line(point=True).encode(
                x=alt.X("lab_date:T", title="Date"),
                y=alt.Y("result_value:Q", title="Value"),
                color="test_name:N",
                tooltip=["test_name", "result_value", "unit", "lab_date"],
            ).properties(height=300)
            st.altair_chart(lab_chart, use_container_width=True)

with tab_claims:
    claims_df = get_patient_claims(patient_id)
    if claims_df.empty:
        st.info("No claims found.")
    else:
        st.dataframe(claims_df, use_container_width=True, hide_index=True)
        status_counts = claims_df.groupby("status").size().reset_index(name="count")
        claim_chart = alt.Chart(status_counts).mark_arc(innerRadius=50).encode(
            theta="count:Q",
            color="status:N",
        ).properties(height=250, title="Claims by Status")
        st.altair_chart(claim_chart, use_container_width=True)

st.divider()

# Similar Patients
st.markdown("### Similar Patients")
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
    st.dataframe(similar, use_container_width=True, hide_index=True)
else:
    st.info("No similar patients found.")
