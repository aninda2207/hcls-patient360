import streamlit as st

from src.data_loader import get_all_patients, get_clinical_notes, get_discharge_summaries, log_audit_event
from src.evidence_retrieval import search_clinical_evidence, format_cited_answer
from src.ui import page_header, patient_options as build_options

CONFIDENCE_COLORS = {"High": "green", "Medium": "orange", "Low": "red"}

patients = get_all_patients()
patient_options = build_options(patients)

page_header("Clinical Q&A", "Ask clinical questions about a patient. Every answer is backed by source citations.",
            icon="forum")

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

def _use_example(q):
    st.session_state["qa_question"] = q
    st.session_state["qa_question_input"] = q


if "qa_question_input" not in st.session_state:
    st.session_state["qa_question_input"] = st.session_state.get("qa_question", "")

with st.container(border=True):
    st.caption(":material/lightbulb: Try an example question")
    with st.container(horizontal=True):
        for i, q in enumerate(example_questions):
            st.button(q, key=f"eq_{i}", width="content", on_click=_use_example, args=(q,))

    question = st.text_input(
        "Your clinical question",
        key="qa_question_input",
        placeholder="e.g., What comorbidities does this patient have?",
        icon=":material/search:",
    )

if question:
    with st.spinner("Searching clinical documentation..."):
        evidence = search_clinical_evidence(patient_id, question)
        answer = format_cited_answer(question, evidence)

    log_audit_event("ASK_QUESTION", patient_id=patient_id,
                    details={"question": question, "evidence_count": len(evidence)})

    with st.container(border=True):
        st.markdown("#### :material/clinical_notes: Answer")
        st.markdown(answer)

    if evidence:
        with st.expander(f"Source documents ({len(evidence)} cited)", icon=":material/library_books:"):
            for item in evidence:
                score = item.get("relevance_score", 0)
                confidence = "High" if score >= 3 else "Medium" if score >= 2 else "Low"
                color = CONFIDENCE_COLORS[confidence]
                st.markdown(
                    f":{color}-badge[{confidence} confidence] **{item['doc_type']}** — {item['section']} "
                    f"(`{item['doc_id']}`)"
                )
                st.text(item["excerpt"])
                st.divider()

st.markdown("#### Patient Documents")
tab_notes, tab_summaries = st.tabs([":material/description: Clinical notes",
                                    ":material/assignment: Discharge summaries"])

with tab_notes:
    notes = get_clinical_notes(patient_id)
    if notes.empty:
        st.info("No clinical notes found.")
    else:
        for _, note in notes.iterrows():
            with st.container(border=True):
                st.markdown(f"**{note['note_type']}** · `{note['note_id']}`")
                st.text(note["raw_text"][:500] + ("..." if len(str(note["raw_text"])) > 500 else ""))

with tab_summaries:
    summaries = get_discharge_summaries(patient_id)
    if summaries.empty:
        st.info("No discharge summaries found.")
    else:
        for _, s in summaries.iterrows():
            with st.container(border=True):
                st.markdown(f"**Discharge Summary** · `{s['summary_id']}`")
                st.text(s["raw_text"][:500] + ("..." if len(str(s["raw_text"])) > 500 else ""))
