import csv
import io
import json

import altair as alt
import pandas as pd
import streamlit as st

from src.components import (
    LACE_MAX, TIER_TEXT, demo_card, esc, gap_card, html_table, page_title, patient_header, render, section_header,
)
from src.data_loader import (
    get_all_patients, get_patient_detail, get_patient_encounters,
    get_patient_care_gaps, get_patient_medications, get_patient_labs, get_patient_claims,
    log_audit_event, run_query,
)
from src.risk_scoring import explain_charlson, explain_lace, get_risk_summary
from src.ui import patient_options as build_options

patients = get_all_patients()
patient_options = build_options(patients)

render(page_title("Patient 360", "Unified clinical, risk and claims view for a single patient"))

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
lace = patient.get("lace_score", 0)
charlson = patient.get("charlson_index", 0)

render(patient_header(patient))
st.write("")
render(f'''<div class="grid-5">
  {demo_card("Age", patient.get("age"))}{demo_card("Gender", patient.get("gender"))}
  {demo_card("Ethnicity", patient.get("ethnicity"))}{demo_card("Region", patient.get("region"))}
  {demo_card("Insurance", patient.get("insurance_type"))}
</div>''')

# ---------- Risk assessment ----------
st.write("")
lace_components = explain_lace(lace, charlson, patient)
factors = explain_charlson(patient.get("active_diagnoses"))
tier_color = TIER_TEXT.get(risk_tier, "#0B1C30")

lace_rows = "".join(
    f'<div class="row"><span><strong>{esc(c["component"])}</strong><br><span style="color:#64748B;">{esc(c["detail"])}</span></span>'
    f'<span class="mono" style="font-weight:600;">+{esc(c["score"])}</span></div>' for c in lace_components
) or '<div class="row">No LACE components available.</div>'
charlson_rows = "".join(
    f'<div class="row"><span><strong>{esc(f["condition"])}</strong> <span class="citation-pill">{esc(f["icd10"])}</span></span>'
    f'<span class="mono" style="font-weight:600;">weight {esc(f["weight"])}</span></div>' for f in factors
) or '<div class="row">No Charlson-weighted conditions found in active diagnoses.</div>'

render(f'''
{section_header("📊", "Risk Assessment", get_risk_summary(patient))}
<div class="grid-3">
  <div class="card-container" style="text-align:center;">
    <div style="font-size:28px;font-weight:700;color:{tier_color};">{esc(risk_tier)}</div>
    <div style="font-size:12px;color:#64748B;">Risk Tier</div>
  </div>
  <div class="card-container" style="text-align:center;">
    <div class="mono" style="font-size:28px;font-weight:600;color:#0B1C30;">{esc(lace)}<span style="font-size:14px;color:#64748B;">/{LACE_MAX}</span></div>
    <div style="font-size:12px;color:#64748B;">LACE Score</div>
  </div>
  <div class="card-container" style="text-align:center;">
    <div class="mono" style="font-size:28px;font-weight:600;color:#0B1C30;">{esc(charlson)}</div>
    <div style="font-size:12px;color:#64748B;">Charlson Index</div>
  </div>
</div>
<div class="grid-2" style="margin-top:12px;">
  <details class="card-container"><summary>LACE Score Breakdown · {esc(lace)}</summary><div style="margin-top:8px;">{lace_rows}</div></details>
  <details class="card-container"><summary>Charlson Contributing Factors · {esc(charlson)}</summary><div style="margin-top:8px;">{charlson_rows}</div></details>
</div>''')

# ---------- Care gaps ----------
st.write("")
gaps_df = get_patient_care_gaps(patient_id)
render(section_header("⚠️", f"Care Gaps ({len(gaps_df)})", "Colour-coded by severity", icon_bg="#FFDAD6"))
if gaps_df.empty:
    st.success("No open care gaps for this patient.", icon=":material/verified:")
else:
    cards = "".join(gap_card(g) for _, g in gaps_df.iterrows())
    render(f'<div class="grid-2">{cards}</div>')

# ---------- Clinical record ----------
st.write("")
render(section_header("🩺", "Clinical Record"))
with st.container(key="card_clinical_record"):
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
            type_counts = enc_df.groupby("encounter_type").size().reset_index(name="count")
            chart = alt.Chart(type_counts).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#1D4ED8").encode(
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
                    color=alt.condition(alt.datum.adherence < 0.8, alt.value("#BA1A1A"), alt.value("#047857")),
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
                theta="count:Q", color="status:N",
            ).properties(height=250, title="Claims by Status")
            st.altair_chart(claim_chart, width="stretch")

# ---------- Similar patients ----------
st.write("")
render(section_header("👥", "Similar Patients", "Closest LACE + Charlson profile"))
similar = run_query("""
    SELECT PATIENT_ID, FIRST_NAME, LAST_NAME, AGE, GENDER, RISK_TIER,
           LACE_SCORE, CHARLSON_INDEX
    FROM PATIENT_360_VIEW
    WHERE PATIENT_ID != %s
    ORDER BY ABS(LACE_SCORE - %s) + ABS(CHARLSON_INDEX - %s)
    LIMIT 5
""", [patient_id, lace, charlson])
if similar.empty:
    st.info("No similar patients found.")
else:
    render(html_table(
        similar,
        [("patient_id", "ID"), ("first_name", "First"), ("last_name", "Last"), ("age", "Age"), ("gender", "Gender"),
         ("risk_tier", "Risk"), ("lace_score", "LACE"), ("charlson_index", "Charlson")],
        badge_cols={"risk_tier"}, num_cols={"patient_id", "age", "lace_score", "charlson_index"},
    ))

# ---------- Export ----------
summary_data = {
    "Patient ID": patient_id,
    "Name": f"{patient['first_name']} {patient['last_name']}",
    "Age": patient.get("age"),
    "Gender": patient.get("gender"),
    "Risk Tier": risk_tier,
    "LACE Score": lace,
    "Charlson Index": charlson,
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
    "risk": {"risk_tier": risk_tier, "lace_score": lace, "charlson_index": charlson},
}

st.write("")
render(section_header("📥", "Export Patient Summary"))
e1, e2, _ = st.columns([1, 1, 3])
e1.download_button(":material/table: Download CSV", csv_buffer.getvalue(),
                   f"patient_{patient_id}_summary.csv", "text/csv", width="stretch")
e2.download_button(":material/data_object: Download JSON", json.dumps(export_json, indent=2, default=str),
                   f"patient_{patient_id}_summary.json", "application/json", width="stretch")
