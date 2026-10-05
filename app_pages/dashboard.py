import pathlib
import sys

import altair as alt
import streamlit as st

from src.data_loader import get_all_patients, get_summary_metrics, get_total_care_gaps, run_query
from src.ui import TIER_HEX, page_header

page_header(
    "Care Coordination Dashboard",
    "Population risk overview and patient registry · Synthetic data only, no real PHI",
    icon="cardiology",
)

metrics = get_summary_metrics()
if not metrics.empty:
    m = metrics.iloc[0]
    total = int(m["total_patients"]) or 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(":material/groups: Total Patients", int(m["total_patients"]), border=True)
    c2.metric(":material/priority_high: High Risk", int(m["high_risk"]), border=True,
              help=f"{int(m['high_risk']) / total:.0%} of population")
    c3.metric(":material/warning: Medium Risk", int(m["medium_risk"]), border=True,
              help=f"{int(m['medium_risk']) / total:.0%} of population")
    c4.metric(":material/check_circle: Low Risk", int(m["low_risk"]), border=True,
              help=f"{int(m['low_risk']) / total:.0%} of population")

risk_dist = run_query("""
    SELECT RISK_TIER, COUNT(*) AS count
    FROM PATIENT_360_VIEW
    GROUP BY RISK_TIER
""")
if not risk_dist.empty:
    chart_col, action_col = st.columns([3, 1])
    with chart_col:
        with st.container(border=True):
            st.markdown("#### Patient Risk Distribution")
            chart = alt.Chart(risk_dist).mark_arc(innerRadius=70, cornerRadius=4).encode(
                theta="count:Q",
                color=alt.Color("risk_tier:N", scale=alt.Scale(
                    domain=list(TIER_HEX.keys()),
                    range=list(TIER_HEX.values()),
                ), title="Risk Tier"),
                tooltip=[alt.Tooltip("risk_tier", title="Tier"), alt.Tooltip("count", title="Patients")],
            ).properties(height=260)
            st.altair_chart(chart, width="stretch")
    with action_col:
        with st.container(border=True, height="stretch"):
            st.markdown("#### Quick Actions")
            st.caption("Add a synthetic patient with encounters, labs, medications, claims and notes.")
            if st.button(":material/person_add: Generate New Patient", type="primary", width="stretch"):
                with st.spinner("Generating new patient..."):
                    try:
                        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
                        from scripts.generate_patient import generate_and_insert
                        from src.data_loader import get_connection, log_audit_event
                        msg = generate_and_insert(conn=get_connection())
                        log_audit_event("GENERATE_PATIENT", patient_id=None, details={"source": "dashboard_button"})
                        st.success(f"New patient added! {msg}")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

st.markdown("#### Patient Registry")
patients_df = get_all_patients()

with st.container(border=True):
    col_risk, col_search, col_count = st.columns([2, 2, 1], vertical_alignment="bottom")

    with col_risk:
        risk_filter = st.multiselect(
            "Risk Tier",
            options=["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM", "LOW"],
        )
    with col_search:
        name_search = st.text_input("Search by name", placeholder="e.g. Smith", icon=":material/search:")

    filtered = patients_df[patients_df["risk_tier"].isin(risk_filter)]
    if name_search:
        mask = (
            filtered["first_name"].str.contains(name_search, case=False, na=False)
            | filtered["last_name"].str.contains(name_search, case=False, na=False)
        )
        filtered = filtered[mask]

    col_count.caption(f"Showing {len(filtered)} of {len(patients_df)} patients")

    if not filtered.empty:
        display_df = filtered[["patient_id", "first_name", "last_name", "age", "gender", "risk_tier", "lace_score", "charlson_index"]].copy()
        display_df.columns = ["ID", "First", "Last", "Age", "Gender", "Risk Tier", "LACE", "Charlson"]

        def color_risk(val):
            return f"color: {TIER_HEX.get(val, '#6B7280')}; font-weight: 700;"

        styled = display_df.style.map(color_risk, subset=["Risk Tier"])
        max_lace = int(display_df["LACE"].max() or 1)
        st.dataframe(
            styled,
            width="stretch",
            hide_index=True,
            height=420,
            column_config={
                "LACE": st.column_config.ProgressColumn("LACE", min_value=0, max_value=max_lace, format="%d"),
                "Charlson": st.column_config.NumberColumn("Charlson", format="%d"),
            },
        )
    else:
        st.info("No patients match the current filters.")

gap_summary = get_total_care_gaps()
if not gap_summary.empty:
    st.markdown("#### Open Care Gaps by Type")
    cols = st.columns(len(gap_summary))
    for i, (_, row) in enumerate(gap_summary.iterrows()):
        cols[i].metric(row["gap_type"], int(row["cnt"]), border=True)
