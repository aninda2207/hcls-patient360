import streamlit as st
import pathlib
import altair as alt

st.set_page_config(
    page_title="HCLS Patient 360",
    page_icon=":material/cardiology:",
    layout="wide",
)

css_path = pathlib.Path(__file__).parent / "static" / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from src.data_loader import get_all_patients, get_summary_metrics, get_total_care_gaps, run_query

st.markdown(
    """
    <div style="padding: 16px; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1);">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 28px;">🏥</span>
            <div>
                <div style="font-size: 18px; font-weight: 700; color: #0B5FFF;">HCLS Patient 360</div>
                <div style="font-size: 11px; color: #94A3B8;">Care Coordinator Copilot &mdash; Synthetic data only, no real PHI</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

metrics = get_summary_metrics()
if not metrics.empty:
    m = metrics.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Patients", int(m["total_patients"]))
    c2.metric("High Risk", int(m["high_risk"]))
    c3.metric("Medium Risk", int(m["medium_risk"]))
    c4.metric("Low Risk", int(m["low_risk"]))

st.divider()

# Risk distribution chart
st.markdown("#### Patient Risk Distribution")
risk_dist = run_query("""
    SELECT RISK_TIER, COUNT(*) AS count
    FROM PATIENT_360_VIEW
    GROUP BY RISK_TIER
""")
if not risk_dist.empty:
    chart_col, action_col = st.columns([3, 1])
    with chart_col:
        chart = alt.Chart(risk_dist).mark_arc(innerRadius=60).encode(
            theta="count:Q",
            color=alt.Color("risk_tier:N", scale=alt.Scale(
                domain=["HIGH", "MEDIUM", "LOW"],
                range=["#DC2626", "#D97706", "#059669"]
            ), title="Risk Tier"),
            tooltip=["risk_tier", "count"]
        ).properties(height=250)
        st.altair_chart(chart, use_container_width=True)
    with action_col:
        st.markdown("#### Quick Actions")
        if st.button(":material/person_add: Generate New Patient", use_container_width=True):
            with st.spinner("Generating new patient..."):
                try:
                    import sys, pathlib
                    sys.path.insert(0, str(pathlib.Path(__file__).parent))
                    from scripts.generate_patient import generate_and_insert
                    from src.data_loader import get_connection, log_audit_event
                    msg = generate_and_insert(conn=get_connection())
                    log_audit_event("GENERATE_PATIENT", patient_id=None, details={"source": "dashboard_button"})
                    st.success(f"New patient added! {msg}")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

st.divider()

col_filter, col_table = st.columns([1, 3])

with col_filter:
    st.markdown("#### Filters")
    patients_df = get_all_patients()

    risk_filter = st.multiselect(
        "Risk Tier",
        options=["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM", "LOW"],
    )

    name_search = st.text_input("Search by name", placeholder="e.g. Smith")

    filtered = patients_df[patients_df["risk_tier"].isin(risk_filter)]
    if name_search:
        mask = (
            filtered["first_name"].str.contains(name_search, case=False, na=False)
            | filtered["last_name"].str.contains(name_search, case=False, na=False)
        )
        filtered = filtered[mask]

with col_table:
    st.markdown("#### Patient Registry")
    st.caption(f"Showing {len(filtered)} of {len(patients_df)} patients")

    if not filtered.empty:
        display_df = filtered[["patient_id", "first_name", "last_name", "age", "gender", "risk_tier", "lace_score", "charlson_index"]].copy()
        display_df.columns = ["ID", "First", "Last", "Age", "Gender", "Risk Tier", "LACE", "Charlson"]

        def color_risk(val):
            colors = {"HIGH": "#DC2626", "MEDIUM": "#D97706", "LOW": "#059669"}
            return f"color: {colors.get(val, '#6B7280')}; font-weight: 700;"

        styled = display_df.style.map(color_risk, subset=["Risk Tier"])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("No patients match the current filters.")

st.divider()

gap_summary = get_total_care_gaps()
if not gap_summary.empty:
    st.markdown("#### Open Care Gaps by Type")
    cols = st.columns(len(gap_summary))
    for i, (_, row) in enumerate(gap_summary.iterrows()):
        cols[i].metric(row["gap_type"], int(row["cnt"]))

st.markdown("---")
st.caption("Navigate to **Patient 360**, **Clinical Q&A**, **Care Actions**, or **Upload Document** using the sidebar.")
