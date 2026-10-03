import streamlit as st
import pathlib

st.set_page_config(page_title="Clinical Q&A", page_icon=":material/forum:", layout="wide")

css_path = pathlib.Path(__file__).parent.parent / "static" / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from src.data_loader import get_all_patients, get_clinical_notes, get_discharge_summaries, log_audit_event
from src.evidence_retrieval import search_clinical_evidence, format_cited_answer

patients = get_all_patients()
patient_options = {
    f"{r['patient_id']} — {r['first_name']} {r['last_name']} ({r['risk_tier']})": r["patient_id"]
    for _, r in patients.iterrows()
}

st.markdown("## :material/forum: Clinical Q&A with Citations")
st.caption("Ask clinical questions about a patient. Every answer is backed by source citations.")

selected = st.selectbox("Select a patient", options=list(patient_options.keys()), key="qa_patient")
if not selected:
    st.stop()

patient_id = patient_options[selected]

example_questions = [
    "What are this patient's active diagnoses?",
    "Has the patient had any emergency visits?",
    "What medications is the patient currently on?",
    "Are there any abnormal lab results?",
    "What was the discharge plan?",
]

st.markdown("#### Example questions")
eq_cols = st.columns(len(example_questions))
for i, q in enumerate(example_questions):
    if eq_cols[i].button(q, key=f"eq_{i}", use_container_width=True):
        st.session_state["qa_question"] = q

question = st.text_input(
    "Your clinical question",
    value=st.session_state.get("qa_question", ""),
    placeholder="e.g., What comorbidities does this patient have?",
)

if question:
    with st.spinner("Searching clinical documentation..."):
        evidence = search_clinical_evidence(patient_id, question)
        answer = format_cited_answer(question, evidence)

    log_audit_event("ASK_QUESTION", patient_id=patient_id,
                    details={"question": question, "evidence_count": len(evidence)})

    st.markdown("---")
    st.markdown(answer)

    if evidence:
        with st.expander(f"Source Documents ({len(evidence)} cited)", expanded=False):
            for item in evidence:
                score = item.get("relevance_score", 0)
                confidence = "High" if score >= 3 else "Medium" if score >= 2 else "Low"
                conf_color = {"High": "green", "Medium": "orange", "Low": "red"}[confidence]
                st.markdown(
                    f"**{item['doc_type']}** — {item['section']} "
                    f"(`{item['doc_id']}`) :{conf_color}[{confidence} confidence]"
                )
                st.text(item["excerpt"])
                st.divider()

st.divider()

with st.expander("Browse all clinical notes for this patient"):
    notes = get_clinical_notes(patient_id)
    if notes.empty:
        st.info("No clinical notes found.")
    else:
        for _, note in notes.iterrows():
            st.markdown(f"**{note['note_type']}** — `{note['note_id']}`")
            st.text(note["raw_text"][:500] + ("..." if len(str(note["raw_text"])) > 500 else ""))
            st.divider()

with st.expander("Browse discharge summaries for this patient"):
    summaries = get_discharge_summaries(patient_id)
    if summaries.empty:
        st.info("No discharge summaries found.")
    else:
        for _, s in summaries.iterrows():
            st.markdown(f"**Discharge Summary** — `{s['summary_id']}`")
            st.text(s["raw_text"][:500] + ("..." if len(str(s["raw_text"])) > 500 else ""))
            st.divider()
