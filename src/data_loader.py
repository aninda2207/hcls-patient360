import pandas as pd
import streamlit as st
import os
import json


@st.cache_resource
def get_connection():
    # In Streamlit-in-Snowflake, use the provided session connection
    try:
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
        return session.connection
    except Exception:
        pass
    # Local development: use snowflake.connector with connection name
    import snowflake.connector
    conn_name = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME") or "default"
    return snowflake.connector.connect(
        connection_name=conn_name,
        client_store_temporary_credential=False,
    )


def _bind(sql, params):
    """Convert %s placeholders to :N numeric bind variables."""
    if not params:
        return sql, params
    i = 0
    out = []
    for ch_idx in range(len(sql)):
        if sql[ch_idx:ch_idx+2] == "%s":
            i += 1
            out.append(f":{i}")
        elif ch_idx > 0 and sql[ch_idx-1:ch_idx+1] == "%s":
            continue
        else:
            out.append(sql[ch_idx])
    return "".join(out), params


def run_query(sql, params=None):
    sql, params = _bind(sql, params)
    with get_connection().cursor() as cur:
        cur.execute("USE DATABASE HCLS_PATIENT360")
        cur.execute("USE SCHEMA PUBLIC")
        cur.execute(sql, params or [])
        rows = cur.fetchall()
        cols = [c[0].lower() for c in cur.description]
    return pd.DataFrame(rows, columns=cols)


def get_all_patients():
    return run_query("""
        SELECT PATIENT_ID, FIRST_NAME, LAST_NAME, AGE, GENDER, RISK_TIER, LACE_SCORE, CHARLSON_INDEX
        FROM PATIENT_360_VIEW
        ORDER BY LACE_SCORE DESC
    """)


def get_patient_detail(patient_id):
    df = run_query("""
        SELECT *
        FROM PATIENT_360_VIEW
        WHERE PATIENT_ID = %s
    """, [patient_id])
    if df.empty:
        return None
    row = df.iloc[0]
    for col in ["active_diagnoses", "active_medications", "recent_labs"]:
        if col in row.index and isinstance(row[col], str):
            try:
                row[col] = json.loads(row[col])
            except (json.JSONDecodeError, TypeError):
                pass
    return row


def get_patient_encounters(patient_id):
    return run_query("""
        SELECT ENCOUNTER_ID, ENCOUNTER_DATE, ENCOUNTER_TYPE, DEPARTMENT, LENGTH_OF_STAY
        FROM ENCOUNTERS
        WHERE PATIENT_ID = %s
        ORDER BY ENCOUNTER_DATE DESC
    """, [patient_id])


def get_patient_care_gaps(patient_id):
    return run_query("""
        SELECT GAP_TYPE, GAP_DESCRIPTION, SEVERITY, RECOMMENDED_ACTION, EVIDENCE_SOURCE
        FROM CARE_GAPS
        WHERE PATIENT_ID = %s
        ORDER BY CASE SEVERITY WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
    """, [patient_id])


def get_patient_claims(patient_id):
    return run_query("""
        SELECT CLAIM_ID, CLAIM_TYPE, AMOUNT, STATUS, DENIAL_REASON, CLAIM_DATE
        FROM CLAIMS
        WHERE PATIENT_ID = %s
        ORDER BY CLAIM_DATE DESC
    """, [patient_id])


def get_patient_medications(patient_id):
    return run_query("""
        SELECT DRUG_NAME, DOSAGE, START_DATE, END_DATE, ADHERENCE
        FROM MEDICATIONS
        WHERE PATIENT_ID = %s
        ORDER BY CASE WHEN END_DATE IS NULL THEN 0 ELSE 1 END, START_DATE DESC
    """, [patient_id])


def get_patient_labs(patient_id):
    return run_query("""
        SELECT TEST_NAME, RESULT_VALUE, UNIT, REFERENCE_RANGE, LAB_DATE, ABNORMAL_FLAG
        FROM LAB_RESULTS
        WHERE PATIENT_ID = %s
        ORDER BY LAB_DATE DESC
    """, [patient_id])


def get_summary_metrics():
    return run_query("""
        SELECT
            COUNT(*) AS total_patients,
            SUM(CASE WHEN RISK_TIER = 'HIGH' THEN 1 ELSE 0 END) AS high_risk,
            SUM(CASE WHEN RISK_TIER = 'MEDIUM' THEN 1 ELSE 0 END) AS medium_risk,
            SUM(CASE WHEN RISK_TIER = 'LOW' THEN 1 ELSE 0 END) AS low_risk
        FROM PATIENT_360_VIEW
    """)


def get_total_care_gaps():
    return run_query("""
        SELECT GAP_TYPE, COUNT(*) AS cnt
        FROM CARE_GAPS
        GROUP BY GAP_TYPE
        ORDER BY cnt DESC
    """)


def get_clinical_notes(patient_id):
    return run_query("""
        SELECT NOTE_ID, NOTE_TYPE, RAW_TEXT, PARSED_JSON, ENCOUNTER_ID
        FROM CLINICAL_NOTES
        WHERE PATIENT_ID = %s
        ORDER BY NOTE_ID DESC
    """, [patient_id])


def get_discharge_summaries(patient_id):
    return run_query("""
        SELECT SUMMARY_ID, RAW_TEXT, PARSED_JSON, ENCOUNTER_ID
        FROM DISCHARGE_SUMMARIES
        WHERE PATIENT_ID = %s
        ORDER BY SUMMARY_ID DESC
    """, [patient_id])


def log_audit_event(action, patient_id=None, details=None, user_id="care_coordinator"):
    try:
        sql = """
            INSERT INTO AUDIT_LOG (USER_ID, ACTION, PATIENT_ID, DETAILS, SESSION_ID)
            VALUES (%s, %s, %s, PARSE_JSON(%s), %s)
        """
        params = [user_id, action, patient_id,
                  json.dumps(details) if details else None,
                  st.session_state.get("_session_id", "unknown")]
        sql, params = _bind(sql, params)
        with get_connection().cursor() as cur:
            cur.execute("USE DATABASE HCLS_PATIENT360")
            cur.execute("USE SCHEMA PUBLIC")
            cur.execute(sql, params)
    except Exception:
        pass
