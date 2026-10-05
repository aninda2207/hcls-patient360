import json

import altair as alt
import pandas as pd
import streamlit as st

from src.data_loader import get_all_patients, get_patient_detail, get_patient_care_gaps, log_audit_event
from src.ui import SEVERITY_COLORS, TIER_COLORS, badge, page_header, patient_options as build_options

patients = get_all_patients()
patient_options = build_options(patients)
option_list = list(patient_options.keys())

page_header("Compare Patients", "Compare two patients side-by-side for care coordination.", icon="compare_arrows")

col1, col2 = st.columns(2)
with col1:
    patient_a_label = st.selectbox("Patient A", options=option_list, key="compare_a", index=0)
with col2:
    patient_b_label = st.selectbox("Patient B", options=option_list, key="compare_b",
                                   index=min(1, len(option_list) - 1))


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


def _summary_card(col, tag, pid, p, gaps):
    with col.container(border=True):
        st.markdown(f"**Patient {tag}** · `{pid}`")
        st.markdown(f"### {p['first_name']} {p['last_name']}")
        st.markdown(badge(p.get("risk_tier"), TIER_COLORS, icon="monitor_heart"))
        k1, k2, k3 = st.columns(3)
        k1.metric("LACE", p.get("lace_score"))
        k2.metric("Charlson", p.get("charlson_index"))
        k3.metric("Care Gaps", len(gaps))


if patient_a_label and patient_b_label and patient_a_label != patient_b_label:
    patient_a_id = patient_options[patient_a_label]
    patient_b_id = patient_options[patient_b_label]

    patient_a = get_patient_detail(patient_a_id)
    patient_b = get_patient_detail(patient_b_id)

    if patient_a is not None and patient_b is not None:
        log_audit_event("COMPARE_PATIENTS", patient_id=None,
                        details={"patient_a": patient_a_id, "patient_b": patient_b_id})

        gaps_a = get_patient_care_gaps(patient_a_id)
        gaps_b = get_patient_care_gaps(patient_b_id)

        sa, sb = st.columns(2)
        _summary_card(sa, "A", patient_a_id, patient_a, gaps_a)
        _summary_card(sb, "B", patient_b_id, patient_b, gaps_b)

        st.markdown("#### Side-by-Side Comparison")
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
                len(gaps_a),
            ],
            f"Patient B ({patient_b_id})": [
                patient_b.get("age"), patient_b.get("gender"), patient_b.get("ethnicity"),
                patient_b.get("region"), patient_b.get("insurance_type"),
                patient_b.get("risk_tier"), patient_b.get("lace_score"),
                patient_b.get("charlson_index"),
                _count(patient_b.get("active_diagnoses")),
                _count(patient_b.get("active_medications")),
                len(gaps_b),
            ],
        }

        df = pd.DataFrame(comparison_data).fillna("—").astype(str)
        st.dataframe(df, width="stretch", hide_index=True, height=(len(df) + 1) * 35 + 3)

        st.markdown("#### Risk Score Comparison")
        risk_data = pd.DataFrame([
            {"Patient": f"A: {patient_a_id}", "Score": patient_a.get("lace_score", 0), "Metric": "LACE"},
            {"Patient": f"A: {patient_a_id}", "Score": patient_a.get("charlson_index", 0), "Metric": "Charlson"},
            {"Patient": f"B: {patient_b_id}", "Score": patient_b.get("lace_score", 0), "Metric": "LACE"},
            {"Patient": f"B: {patient_b_id}", "Score": patient_b.get("charlson_index", 0), "Metric": "Charlson"},
        ])
        chart = alt.Chart(risk_data).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("Metric:N", axis=alt.Axis(labelAngle=0)),
            y="Score:Q",
            color=alt.Color("Patient:N", scale=alt.Scale(range=["#0B5FFF", "#94A3B8"])),
            xOffset="Patient:N",
            tooltip=["Patient", "Metric", "Score"],
        ).properties(height=300)
        with st.container(border=True):
            st.altair_chart(chart, width="stretch")

        st.markdown("#### Care Gaps Comparison")
        gc1, gc2 = st.columns(2)
        for col, tag, gaps in ((gc1, "A", gaps_a), (gc2, "B", gaps_b)):
            with col.container(border=True):
                st.markdown(f"**Patient {tag}** · {len(gaps)} gaps")
                if not gaps.empty:
                    for _, g in gaps.iterrows():
                        st.markdown(f"{badge(g['severity'], SEVERITY_COLORS)} {g['gap_type']}")
                else:
                    st.info("No care gaps")
elif patient_a_label == patient_b_label:
    st.warning("Select two different patients to compare.")
