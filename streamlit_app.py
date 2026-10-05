import pathlib

import streamlit as st

st.set_page_config(
    page_title="HCLS Patient 360",
    page_icon=":material/cardiology:",
    layout="wide",
)

css_path = pathlib.Path(__file__).parent / "static" / "styles.css"
if css_path.exists():
    # st.html with only a <style> tag applies CSS without rendering any text
    st.html(f"<style>{css_path.read_text()}</style>")

pages = {
    "Overview": [
        st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    ],
    "Patient care": [
        st.Page("app_pages/patient_360.py", title="Patient 360", icon=":material/person:"),
        st.Page("app_pages/clinical_qa.py", title="Clinical Q&A", icon=":material/forum:"),
        st.Page("app_pages/care_actions.py", title="Care Actions", icon=":material/task_alt:"),
        st.Page("app_pages/compare_patients.py", title="Compare Patients", icon=":material/compare_arrows:"),
    ],
    "Data & compliance": [
        st.Page("app_pages/add_patient.py", title="Add Patient", icon=":material/person_add:"),
        st.Page("app_pages/upload_document.py", title="Upload Document", icon=":material/upload_file:"),
        st.Page("app_pages/audit_log.py", title="Audit Log", icon=":material/history:"),
    ],
}

nav = st.navigation(pages)

with st.sidebar:
    st.caption(":material/shield: Synthetic data only — no real PHI")

nav.run()
