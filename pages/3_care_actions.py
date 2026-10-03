import streamlit as st
import pathlib

st.set_page_config(page_title="Care Actions", page_icon=":material/task_alt:", layout="wide")

css_path = pathlib.Path(__file__).parent.parent / "static" / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from src.data_loader import get_all_patients, get_patient_detail, get_patient_care_gaps, log_audit_event
from src.care_gaps import generate_care_recommendations
from src.risk_scoring import get_risk_summary

patients = get_all_patients()
patient_options = {
    f"{r['patient_id']} — {r['first_name']} {r['last_name']} ({r['risk_tier']})": r["patient_id"]
    for _, r in patients.iterrows()
}

st.markdown("## :material/task_alt: Recommended Care Actions")
st.caption("Next-best-action recommendations with evidence and explanations.")

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
    st.error(risk_summary)
elif tier == "MEDIUM":
    st.warning(risk_summary)
else:
    st.success(risk_summary)

st.divider()

gaps_df = get_patient_care_gaps(patient_id)
recommendations = generate_care_recommendations(patient, gaps_df)

log_audit_event("GENERATE_ACTIONS", patient_id=patient_id,
                details={"recommendation_count": len(recommendations)})

if not recommendations:
    st.success("No outstanding care actions for this patient.")
    st.stop()

st.markdown(f"### {len(recommendations)} Recommended Action(s)")

priority_colors = {"Urgent": "#DC2626", "High": "#EA580C", "Medium": "#D97706", "Low": "#059669"}

for i, rec in enumerate(recommendations, 1):
    priority = rec.get("priority", "Medium")
    priority_color = priority_colors.get(priority, "#6B7280")

    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"#### Action {i}: {rec['action']}")
            st.markdown(f"**Rationale:** {rec['rationale']}")
            st.caption(f"Evidence: {rec['evidence']}")
        with c2:
            st.markdown(
                f"<div style='text-align:center;padding:8px;border-radius:8px;"
                f"background:{priority_color}15;border:1px solid {priority_color};'>"
                f"<span style='font-weight:700;color:{priority_color};'>{priority}</span></div>",
                unsafe_allow_html=True,
            )

st.divider()
st.caption(
    "All recommendations are generated from structured data and clinical documentation. "
    "Each recommendation includes the evidence source for auditability."
)
