import streamlit as st
import pathlib

st.set_page_config(page_title="Audit Log", page_icon=":material/history:", layout="wide")

css_path = pathlib.Path(__file__).parent.parent / "static" / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from src.data_loader import run_query

st.markdown("## :material/history: Audit Log")
st.caption("Track all user interactions for compliance and audit purposes.")

col1, col2, col3 = st.columns(3)
with col1:
    action_filter = st.multiselect(
        "Action Type",
        ["VIEW_PATIENT", "ASK_QUESTION", "GENERATE_ACTIONS", "UPLOAD_DOCUMENT", "GENERATE_PATIENT"],
        default=["VIEW_PATIENT", "ASK_QUESTION", "GENERATE_ACTIONS", "UPLOAD_DOCUMENT", "GENERATE_PATIENT"],
    )
with col2:
    patient_filter = st.text_input("Patient ID (optional)")
with col3:
    limit = st.selectbox("Records", [50, 100, 200, 500], index=1)

where_clauses = []
params = []

if action_filter:
    placeholders = ",".join(["%s"] * len(action_filter))
    where_clauses.append(f"ACTION IN ({placeholders})")
    params.extend(action_filter)

if patient_filter:
    where_clauses.append("PATIENT_ID = %s")
    params.append(patient_filter)

where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

try:
    audit_df = run_query(f"""
        SELECT TIMESTAMP, USER_ID, ACTION, PATIENT_ID, DETAILS
        FROM AUDIT_LOG
        {where_sql}
        ORDER BY TIMESTAMP DESC
        LIMIT %s
    """, params + [limit])

    if audit_df.empty:
        st.info("No audit records found. Actions will appear here as users interact with the app.")
    else:
        st.dataframe(audit_df, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(audit_df)} records")
except Exception:
    st.info("Audit log table not yet created. It will be initialized on first use.")
