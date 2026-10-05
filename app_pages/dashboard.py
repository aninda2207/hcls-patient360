import pathlib
import sys

import altair as alt
import streamlit as st

from src.components import LACE_MAX, html_table, metric_card, page_title, render, section_header, status_pills
from src.data_loader import get_all_patients, get_summary_metrics, get_total_care_gaps, run_query
from src.ui import TIER_HEX

render(status_pills([
    "HCLS Patient 360 — Care Coordinator Copilot",
    "Synthetic Cohort: Zero PHI Active",
    "Document Parsing + Evidence Retrieval",
]))
render(page_title("Care Coordination Dashboard", "Population risk overview and patient registry"))

metrics = get_summary_metrics()
m = metrics.iloc[0] if not metrics.empty else {}
total = int(m.get("total_patients", 0) or 0)
high = int(m.get("high_risk", 0) or 0)

doc_counts = run_query("""
    SELECT (SELECT COUNT(*) FROM CLINICAL_NOTES) AS notes,
           (SELECT COUNT(*) FROM DISCHARGE_SUMMARIES) AS summaries,
           (SELECT COUNT(*) FROM REGULATORY_FILINGS) AS filings,
           (SELECT COUNT(*) FROM CARE_GAPS) AS gaps_all,
           (SELECT COUNT(*) FROM CARE_GAPS WHERE SEVERITY = 'High') AS gaps_high,
           (SELECT AVG(LACE_SCORE) FROM PATIENT_360_VIEW) AS mean_lace
""").iloc[0]
docs = int(doc_counts["notes"] + doc_counts["summaries"] + doc_counts["filings"])
gaps_all = int(doc_counts["gaps_all"] or 0)
gaps_high = int(doc_counts["gaps_high"] or 0)
mean_lace = float(doc_counts["mean_lace"] or 0)

render(f'''<div class="grid-4">
  {metric_card("Synthetic Cohort", total, f"Enrolled lives · {high} high risk", "👥", "#0037B0", 100)}
  {metric_card("Clinical Docs", docs, f"{int(doc_counts['notes'])} notes · {int(doc_counts['summaries'])} summaries", "📄", "#2C2ABC", 100)}
  {metric_card("Care Gaps Flagged", gaps_high, f"High severity of {gaps_all} open gaps", "⚠️", "#BA1A1A", gaps_high / gaps_all * 100 if gaps_all else 0)}
  {metric_card("Mean LACE Risk", f"{mean_lace:.1f}", f"Out of {LACE_MAX} · 30-day readmission", "📊", "#565E74", mean_lace / LACE_MAX * 100)}
</div>''')

st.write("")
risk_dist = run_query("SELECT RISK_TIER, COUNT(*) AS count FROM PATIENT_360_VIEW GROUP BY RISK_TIER")
chart_col, action_col = st.columns([3, 1])
with chart_col:
    with st.container(key="card_risk_dist", height="stretch"):
        render(section_header("🍩", "Patient Risk Distribution", "Share of cohort by readmission risk tier"))
        if not risk_dist.empty:
            chart = alt.Chart(risk_dist).mark_arc(innerRadius=70, cornerRadius=4).encode(
                theta="count:Q",
                color=alt.Color("risk_tier:N", scale=alt.Scale(domain=list(TIER_HEX), range=list(TIER_HEX.values())),
                                title="Risk Tier"),
                tooltip=[alt.Tooltip("risk_tier", title="Tier"), alt.Tooltip("count", title="Patients")],
            ).properties(height=240)
            st.altair_chart(chart, width="stretch")
with action_col:
    with st.container(key="card_quick_actions", height="stretch"):
        render(section_header("⚡", "Quick Actions", "Grow or enrich the cohort"))
        if st.button(":material/person_add: Generate New Patient", type="primary", width="stretch"):
            with st.spinner("Generating new patient..."):
                try:
                    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
                    from scripts.generate_patient import generate_and_insert
                    from src.data_loader import get_connection, log_audit_event
                    msg = generate_and_insert(conn=get_connection())
                    log_audit_event("GENERATE_PATIENT", patient_id=None, details={"source": "dashboard_button"})
                    st.toast(f"New patient added! {msg}", icon=":material/check_circle:")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        if st.button(":material/upload_file: Upload Document", width="stretch"):
            st.switch_page("app_pages/upload_document.py")
        if st.button(":material/person_add_alt: Add Patient Manually", width="stretch"):
            st.switch_page("app_pages/add_patient.py")

st.write("")
patients_df = get_all_patients()
with st.container(key="card_registry"):
    render(section_header("🗂️", "Patient Registry", "Sorted by LACE score, highest risk first"))
    col_risk, col_search, col_count = st.columns([2, 2, 1], vertical_alignment="bottom")
    risk_filter = col_risk.multiselect("Risk Tier", ["HIGH", "MEDIUM", "LOW"], default=["HIGH", "MEDIUM", "LOW"])
    name_search = col_search.text_input("Search by name", placeholder="e.g. Smith", icon=":material/search:")

    filtered = patients_df[patients_df["risk_tier"].isin(risk_filter)]
    if name_search:
        filtered = filtered[
            filtered["first_name"].str.contains(name_search, case=False, na=False)
            | filtered["last_name"].str.contains(name_search, case=False, na=False)
        ]
    col_count.caption(f"Showing {len(filtered)} of {len(patients_df)} patients")

    if filtered.empty:
        st.info("No patients match the current filters.")
    else:
        render(html_table(
            filtered,
            [("patient_id", "ID"), ("first_name", "First"), ("last_name", "Last"), ("age", "Age"),
             ("gender", "Gender"), ("risk_tier", "Risk"), ("lace_score", "LACE"), ("charlson_index", "Charlson")],
            badge_cols={"risk_tier"}, num_cols={"patient_id", "age", "lace_score", "charlson_index"},
        ))

gap_summary = get_total_care_gaps()
if not gap_summary.empty:
    st.write("")
    render(section_header("⚠️", "Open Care Gaps by Type", f"{gaps_all} gaps across the cohort", icon_bg="#FFDAD6"))
    max_cnt = int(gap_summary["cnt"].max())
    cards = "".join(metric_card(r["gap_type"], int(r["cnt"]), "Open gaps", "•", "#BA1A1A", int(r["cnt"]) / max_cnt * 100)
                    for _, r in gap_summary.iterrows())
    render(f'<div class="grid-4">{cards}</div>')
