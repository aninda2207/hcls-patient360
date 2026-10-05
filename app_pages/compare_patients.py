import altair as alt
import pandas as pd
import streamlit as st

from src.components import count_items, esc, gap_card, page_title, render, risk_badge, section_header
from src.data_loader import get_all_patients, get_patient_care_gaps, get_patient_detail, log_audit_event
from src.ui import patient_options as build_options

patients = get_all_patients()
patient_options = build_options(patients)
option_list = list(patient_options.keys())

render(page_title("Compare Patients", "Compare two patients side-by-side for care coordination"))

col1, col2 = st.columns(2)
with col1.container(key="card_sel_a"):
    render(section_header("🅰️", "Patient A"))
    patient_a_label = st.selectbox("Patient A", options=option_list, key="compare_a", index=0, label_visibility="collapsed")
with col2.container(key="card_sel_b"):
    render(section_header("🅱️", "Patient B", icon_bg="#DAE2FD"))
    patient_b_label = st.selectbox("Patient B", options=option_list, key="compare_b",
                                   index=min(1, len(option_list) - 1), label_visibility="collapsed")

if patient_a_label == patient_b_label:
    st.warning("Select two different patients to compare.")
    st.stop()

patient_a_id = patient_options[patient_a_label]
patient_b_id = patient_options[patient_b_label]
patient_a = get_patient_detail(patient_a_id)
patient_b = get_patient_detail(patient_b_id)
if patient_a is None or patient_b is None:
    st.error("Patient not found.")
    st.stop()

log_audit_event("COMPARE_PATIENTS", patient_id=None, details={"patient_a": patient_a_id, "patient_b": patient_b_id})
gaps_a = get_patient_care_gaps(patient_a_id)
gaps_b = get_patient_care_gaps(patient_b_id)


def _row(label, a, b, raw=False):
    va, vb = (a, b) if raw else (esc(a), esc(b))
    return f"<tr><td style='font-weight:600;color:#434655;'>{esc(label)}</td><td>{va}</td><td>{vb}</td></tr>"


rows = "".join([
    _row("Name", f"{patient_a['first_name']} {patient_a['last_name']}", f"{patient_b['first_name']} {patient_b['last_name']}"),
    _row("Age", patient_a.get("age"), patient_b.get("age")),
    _row("Gender", patient_a.get("gender"), patient_b.get("gender")),
    _row("Ethnicity", patient_a.get("ethnicity"), patient_b.get("ethnicity")),
    _row("Region", patient_a.get("region"), patient_b.get("region")),
    _row("Insurance", patient_a.get("insurance_type"), patient_b.get("insurance_type")),
    _row("Risk Tier", risk_badge(patient_a.get("risk_tier")), risk_badge(patient_b.get("risk_tier")), raw=True),
    _row("LACE Score", patient_a.get("lace_score"), patient_b.get("lace_score")),
    _row("Charlson Index", patient_a.get("charlson_index"), patient_b.get("charlson_index")),
    _row("Active Diagnoses", count_items(patient_a.get("active_diagnoses")), count_items(patient_b.get("active_diagnoses"))),
    _row("Active Medications", count_items(patient_a.get("active_medications")), count_items(patient_b.get("active_medications"))),
    _row("Care Gaps", len(gaps_a), len(gaps_b)),
])
st.write("")
render(f'''
<div class="card-container">
  {section_header("⚖️", "Side-by-Side Comparison")}
  <div class="table-wrap" style="max-height:none;"><table class="data-table">
    <thead><tr><th>Attribute</th><th>Patient A · {esc(patient_a_id)}</th><th>Patient B · {esc(patient_b_id)}</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
</div>''')

st.write("")
risk_data = pd.DataFrame([
    {"Patient": f"A: {patient_a_id}", "Score": patient_a.get("lace_score", 0), "Metric": "LACE"},
    {"Patient": f"A: {patient_a_id}", "Score": patient_a.get("charlson_index", 0), "Metric": "Charlson"},
    {"Patient": f"B: {patient_b_id}", "Score": patient_b.get("lace_score", 0), "Metric": "LACE"},
    {"Patient": f"B: {patient_b_id}", "Score": patient_b.get("charlson_index", 0), "Metric": "Charlson"},
])
with st.container(key="card_risk_chart"):
    render(section_header("📊", "Risk Score Comparison"))
    chart = alt.Chart(risk_data).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Metric:N", axis=alt.Axis(labelAngle=0)),
        y="Score:Q",
        color=alt.Color("Patient:N", scale=alt.Scale(range=["#1D4ED8", "#94A3B8"])),
        xOffset="Patient:N",
        tooltip=["Patient", "Metric", "Score"],
    ).properties(height=300)
    st.altair_chart(chart, width="stretch")

st.write("")
render(section_header("⚠️", "Care Gaps Comparison", icon_bg="#FFDAD6"))
blocks = []
for tag, pid, gaps in (("A", patient_a_id, gaps_a), ("B", patient_b_id, gaps_b)):
    body = "".join(gap_card(g) for _, g in gaps.iterrows()) or \
        '<div style="font-size:13px;color:#047857;">No open care gaps.</div>'
    blocks.append(f'<div class="card-container"><div class="card-title" style="margin-bottom:10px;">'
                  f'Patient {tag} · {esc(pid)} ({len(gaps)} gaps)</div>{body}</div>')
render(f'<div class="grid-2">{"".join(blocks)}</div>')
