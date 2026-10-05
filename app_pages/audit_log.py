import streamlit as st

from src.data_loader import run_query
from src.ui import page_header

ACTIONS = ["VIEW_PATIENT", "ASK_QUESTION", "GENERATE_ACTIONS", "UPLOAD_DOCUMENT", "GENERATE_PATIENT"]

page_header("Audit Log", "Track all user interactions for compliance and audit purposes.", icon="history")

with st.container(border=True):
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        action_filter = st.multiselect("Action Type", ACTIONS, default=ACTIONS)
    with col2:
        patient_filter = st.text_input("Patient ID (optional)", placeholder="e.g. P00089", icon=":material/search:")
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
        st.dataframe(
            audit_df,
            width="stretch",
            hide_index=True,
            column_config={
                "timestamp": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm:ss"),
                "user_id": "User",
                "action": "Action",
                "patient_id": "Patient",
                "details": st.column_config.JsonColumn("Details") if hasattr(st.column_config, "JsonColumn") else "Details",
            },
        )
        st.caption(f"Showing {len(audit_df)} records")
except Exception:
    st.info("Audit log table not yet created. It will be initialized on first use.")
