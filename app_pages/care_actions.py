import streamlit as st

from src.data_loader import get_all_patients, get_patient_detail, get_patient_care_gaps, log_audit_event
from src.care_gaps import generate_care_recommendations
from src.risk_scoring import get_risk_summary
from src.ui import PRIORITY_COLORS, badge, page_header, patient_options as build_options

patients = get_all_patients()
patient_options = build_options(patients)

page_header("Care Actions", "Next-best-action recommendations with evidence and explanations.", icon="task_alt")

selected = st.selectbox("Select a patient", options=list(patient_options.keys()), key="action_patient")
if not selected:
    st.stop()

patient_id = patient_options[selected]
patient = get_patient_detail(patient_id)
if patient is None:
    st.error("Patient not found.")
    st.stop()

risk_summary = get_risk_summary(patient)
tier = patient.get("risk_tier", "LOW")
if tier == "HIGH":
    st.error(risk_summary, icon=":material/priority_high:")
elif tier == "MEDIUM":
    st.warning(risk_summary, icon=":material/warning:")
else:
    st.success(risk_summary, icon=":material/check_circle:")

gaps_df = get_patient_care_gaps(patient_id)
recommendations = generate_care_recommendations(patient, gaps_df)

log_audit_event("GENERATE_ACTIONS", patient_id=patient_id,
                details={"recommendation_count": len(recommendations)})

if not recommendations:
    st.success("No outstanding care actions for this patient.", icon=":material/verified:")
    st.stop()

st.markdown(f"#### {len(recommendations)} Recommended Action(s)")

counts = {p: sum(1 for r in recommendations if r.get("priority", "Medium") == p) for p in PRIORITY_COLORS}
present = [p for p in PRIORITY_COLORS if counts[p]]
if present:
    cols = st.columns(len(present))
    for col, p in zip(cols, present):
        col.metric(p, counts[p], border=True)

for i, rec in enumerate(recommendations, 1):
    priority = rec.get("priority", "Medium")

    with st.container(border=True):
        c1, c2 = st.columns([5, 1], vertical_alignment="top")
        with c1:
            st.markdown(f"##### {i}. {rec['action']}")
            st.markdown(f"**Rationale:** {rec['rationale']}")
            st.caption(f":material/fact_check: Evidence: {rec['evidence']}")
        with c2:
            st.markdown(badge(priority, PRIORITY_COLORS, icon="flag"))

st.caption(
    "All recommendations are generated from structured data and clinical documentation. "
    "Each recommendation includes the evidence source for auditability."
)
