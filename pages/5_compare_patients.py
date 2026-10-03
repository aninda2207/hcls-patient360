import streamlit as st
import pathlib
import pandas as pd
import altair as alt

st.set_page_config(page_title="Compare Patients", page_icon=":material/compare:", layout="wide")

css_path = pathlib.Path(__file__).parent.parent / "static" / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from src.data_loader import get_all_patients, get_patient_detail, get_patient_care_gaps, log_audit_event

patients = get_all_patients()
patient_options = {
    f"{r['patient_id']} — {r['first_name']} {r['last_name']} ({r['risk_tier']})": r["patient_id"]
    for _, r in patients.iterrows()
}
option_list = list(patient_options.keys())

st.markdown("## :material/compare: Patient Comparison")
st.caption("Compare two patients side-by-side for care coordination.")

col1, col2 = st.columns(2)
with col1:
    patient_a_label = st.selectbox("Patient A", options=option_list, key="compare_a", index=0)
with col2:
    patient_b_label = st.selectbox("Patient B", options=option_list, key="compare_b",
                                    index=min(1, len(option_list) - 1))

if patient_a_label and patient_b_label and patient_a_label != patient_b_label:
    patient_a_id = patient_options[patient_a_label]
    patient_b_id = patient_options[patient_b_label]

    patient_a = get_patient_detail(patient_a_id)
    patient_b = get_patient_detail(patient_b_id)

    if patient_a is not None and patient_b is not None:
        log_audit_event("COMPARE_PATIENTS", patient_id=None,
                        details={"patient_a": patient_a_id, "patient_b": patient_b_id})

        st.markdown("### Side-by-Side Comparison")

        import json

        def _count(val):
            if val is None:
                return 0
            if isinstance(val, str):
                try:
                    return len(json.loads(val))
                except (json.JSONDecodeError, TypeError):
                    return 0
            if isinstance(val, list):
                return len(val)
            return 0

        comparison_data = {
            "Attribute": ["Age", "Gender", "Ethnicity", "Region", "Insurance",
                          "Risk Tier", "LACE Score", "Charlson Index",
                          "Active Diagnoses", "Active Medications", "Care Gaps"],
            f"Patient A ({patient_a_id})": [
                patient_a.get("age"), patient_a.get("gender"), patient_a.get("ethnicity"),
                patient_a.get("region"), patient_a.get("insurance_type"),
                patient_a.get("risk_tier"), patient_a.get("lace_score"),
                patient_a.get("charlson_index"),
                _count(patient_a.get("active_diagnoses")),
                _count(patient_a.get("active_medications")),
                len(get_patient_care_gaps(patient_a_id)),
            ],
            f"Patient B ({patient_b_id})": [
                patient_b.get("age"), patient_b.get("gender"), patient_b.get("ethnicity"),
                patient_b.get("region"), patient_b.get("insurance_type"),
                patient_b.get("risk_tier"), patient_b.get("lace_score"),
                patient_b.get("charlson_index"),
                _count(patient_b.get("active_diagnoses")),
                _count(patient_b.get("active_medications")),
                len(get_patient_care_gaps(patient_b_id)),
            ],
        }

        df = pd.DataFrame(comparison_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### Risk Score Comparison")
        risk_data = pd.DataFrame([
            {"Patient": f"A: {patient_a_id}", "Score": patient_a.get("lace_score", 0), "Metric": "LACE"},
            {"Patient": f"A: {patient_a_id}", "Score": patient_a.get("charlson_index", 0), "Metric": "Charlson"},
            {"Patient": f"B: {patient_b_id}", "Score": patient_b.get("lace_score", 0), "Metric": "LACE"},
            {"Patient": f"B: {patient_b_id}", "Score": patient_b.get("charlson_index", 0), "Metric": "Charlson"},
        ])
        chart = alt.Chart(risk_data).mark_bar().encode(
            x="Metric:N",
            y="Score:Q",
            color="Patient:N",
            xOffset="Patient:N",
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)

        st.markdown("### Care Gaps Comparison")
        gaps_a = get_patient_care_gaps(patient_a_id)
        gaps_b = get_patient_care_gaps(patient_b_id)
        gc1, gc2 = st.columns(2)
        with gc1:
            st.markdown(f"**Patient A** ({len(gaps_a)} gaps)")
            if not gaps_a.empty:
                st.dataframe(gaps_a[["gap_type", "severity"]], use_container_width=True, hide_index=True)
            else:
                st.info("No care gaps")
        with gc2:
            st.markdown(f"**Patient B** ({len(gaps_b)} gaps)")
            if not gaps_b.empty:
                st.dataframe(gaps_b[["gap_type", "severity"]], use_container_width=True, hide_index=True)
            else:
                st.info("No care gaps")
elif patient_a_label == patient_b_label:
    st.warning("Select two different patients to compare.")
