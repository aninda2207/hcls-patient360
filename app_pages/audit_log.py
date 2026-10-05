import json

import streamlit as st

from src.components import html_table, page_title, render, section_header
from src.data_loader import run_query

ACTIONS = ["VIEW_PATIENT", "ASK_QUESTION", "GENERATE_ACTIONS", "UPLOAD_DOCUMENT", "GENERATE_PATIENT",
           "ADD_PATIENT", "COMPARE_PATIENTS", "ADD_TO_CARE_PLAN", "ACCEPT_ACTION", "MODIFY_ACTION",
           "AUTHORIZE_ACTIONS"]

render(page_title("Audit Log", "Track all user interactions for compliance and audit purposes"))

with st.container(key="card_audit_filters"):
    col1, col2, col3 = st.columns([3, 2, 1])
    action_filter = col1.multiselect("Action Type", ACTIONS, default=ACTIONS)
    patient_filter = col2.text_input("Patient ID (optional)", placeholder="e.g. P00089", icon=":material/search:")
    limit = col3.selectbox("Records", [50, 100, 200, 500], index=1)

where_clauses, params = [], []
if action_filter:
    where_clauses.append(f"ACTION IN ({','.join(['%s'] * len(action_filter))})")
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
except Exception:
    st.info("Audit log table not yet created. It will be initialized on first use.")
    st.stop()

st.write("")
if audit_df.empty:
    st.info("No audit records found. Actions will appear here as users interact with the app.")
    st.stop()

audit_df["timestamp"] = audit_df["timestamp"].astype(str).str[:19]
with st.container(key="card_audit_table"):
    render(section_header("🧾", "Audit Trail", f"Showing {len(audit_df)} records"))
    render(html_table(
        audit_df,
        [("timestamp", "Timestamp"), ("user_id", "User"), ("action", "Action"), ("patient_id", "Patient"),
         ("details", "Details")],
        num_cols={"timestamp", "patient_id"}, wrap_cols={"details"}, max_height=560,
    ))

records = audit_df.to_dict(orient="records")
for r in records:
    if isinstance(r.get("details"), str):
        try:
            r["details"] = json.loads(r["details"])
        except json.JSONDecodeError:
            pass
st.download_button(":material/download: Export JSON Audit Trail", json.dumps(records, indent=2, default=str),
                   "audit_trail.json", "application/json")
