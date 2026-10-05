import time
import uuid

import pandas as pd
import streamlit as st

from src.components import citation_pill, esc, page_title, render, risk_badge, sha256, section_header, initials
from src.data_loader import (
    get_all_patients, get_clinical_notes, get_discharge_summaries, get_patient_detail, get_patient_labs,
    log_audit_event, run_query,
)
from src.evidence_retrieval import format_cited_answer, search_clinical_evidence
from src.ui import patient_options as build_options

patients = get_all_patients()
patient_options = build_options(patients)

render(page_title("Clinical Q&A", "Ask clinical questions about a patient. Every answer is grounded in cited source documents."))

selected = st.selectbox("Select a patient", options=list(patient_options.keys()), key="qa_patient")
if not selected:
    st.stop()

patient_id = patient_options[selected]
patient = get_patient_detail(patient_id)
if patient is None:
    st.error("Patient not found.")
    st.stop()

# ---------- Patient context strip ----------
tier = patient.get("risk_tier", "LOW")
avatar_bg = {"HIGH": "#FFDAD6", "MEDIUM": "#FFFBEB", "LOW": "#ECFDF5"}.get(tier, "#E5EEFF")
render(f'''
<div class="card-container" style="padding:12px 16px;display:flex;align-items:center;gap:16px;justify-content:space-between;flex-wrap:wrap;">
  <div style="display:flex;align-items:center;gap:12px;">
    <div style="width:36px;height:36px;border-radius:8px;background:{avatar_bg};display:flex;align-items:center;justify-content:center;font-weight:700;color:#0B1C30;">{esc(initials(patient.get("first_name"), patient.get("last_name")))}</div>
    <div>
      <div style="font-size:16px;font-weight:600;color:#0B1C30;">{esc(patient.get("first_name"))} {esc(patient.get("last_name"))}</div>
      <div style="font-size:12px;color:#434655;">{esc(patient_id)} · {esc(patient.get("age"))} y · {esc(patient.get("gender"))} · {esc(patient.get("insurance_type"))}</div>
    </div>
  </div>
  <div style="display:flex;gap:8px;align-items:center;">
    {risk_badge(tier)}
    <span class="score-pill">LACE: {esc(patient.get("lace_score"))}</span>
    <span class="score-pill">Charlson: {esc(patient.get("charlson_index"))}</span>
  </div>
</div>''')
st.write("")

# ---------- Query composer ----------
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

with st.container(key="card_composer"):
    qcol, bcol = st.columns([4, 1.8], vertical_alignment="bottom")
    question = qcol.text_input(
        "Your clinical question",
        key="qa_question_input",
        placeholder="Ask a clinical or regulatory question...",
        icon=":material/search:",
        label_visibility="collapsed",
    )
    bcol.button(":material/manage_search: Retrieve with Citations", type="primary", width="stretch")
    with st.container(horizontal=True):
        for i, q in enumerate(example_questions):
            st.button(q, key=f"chip_{i}", width="content", on_click=_use_example, args=(q,))

if question:
    t0 = time.perf_counter()
    with st.spinner("Searching clinical documentation..."):
        evidence = search_clinical_evidence(patient_id, question)
        t_search = time.perf_counter()
        answer = format_cited_answer(question, evidence)
    t_end = time.perf_counter()
    exec_id = f"exec_{uuid.uuid4().hex[:8]}"
    keywords = [w for w in question.lower().split() if len(w) > 3]

    log_audit_event("ASK_QUESTION", patient_id=patient_id,
                    details={"question": question, "evidence_count": len(evidence), "execution_id": exec_id})

    # ---------- Orchestration trace ----------
    render(f'''
    <details class="card-container" style="margin-top:4px;">
      <summary>Retrieval Trace [Execution ID: {exec_id}] — completed in {(t_end - t0) * 1000:.0f} ms</summary>
      <div class="grid-4" style="margin-top:12px;">
        <div class="trace-step"><div class="k">1 · Parse intent</div><div class="m">{len(keywords)} keyword(s): {esc(", ".join(keywords[:5]))}</div><div class="ok">✓</div></div>
        <div class="trace-step"><div class="k">2 · Document search</div><div class="m">notes · summaries · filings · {(t_search - t0) * 1000:.0f} ms</div><div class="ok">✓</div></div>
        <div class="trace-step"><div class="k">3 · Rank evidence</div><div class="m">top {len(evidence)} chunk(s) kept</div><div class="ok">✓</div></div>
        <div class="trace-step"><div class="k">4 · Grounded synthesis</div><div class="m">{(t_end - t_search) * 1000:.0f} ms</div><div class="ok">✓</div></div>
      </div>
    </details>''')

    # ---------- Synthesized answer ----------
    top_score = max((e["relevance_score"] for e in evidence), default=0)
    coverage = (top_score / len(keywords) * 100) if keywords else 0
    with st.container(key="answer_box"):
        render(f'''
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <div style="display:flex;align-items:center;gap:8px;"><span style="color:#6366F1;">✅</span>
            <span style="font-size:18px;font-weight:600;color:#0B1C30;">Grounded Clinical Synthesis</span></div>
          <div style="display:flex;gap:8px;">
            <span class="confidence-badge">Keyword coverage: {coverage:.0f}%</span>
            <span class="confidence-badge">{len(evidence)} Provenance Anchor(s)</span>
          </div>
        </div>''')
        st.markdown(answer)

        labs = get_patient_labs(patient_id)
        abnormal = labs[labs["abnormal_flag"].astype(str).str.upper().isin(["TRUE", "Y", "YES", "H", "L", "1"])] \
            if not labs.empty and "abnormal_flag" in labs else pd.DataFrame()
        if not abnormal.empty:
            pills = " ".join(citation_pill(f"{r['test_name']} {r['result_value']} {r['unit'] or ''}")
                             for _, r in abnormal.head(4).iterrows())
            render(f'''
            <div class="callout-warn"><span style="color:#BA1A1A;font-size:22px;">⚠️</span>
              <div><div style="font-weight:600;color:#BA1A1A;">Abnormal Lab Results on File ({len(abnormal)})</div>
              <div style="font-size:13px;color:#0B1C30;margin-top:4px;">Review before acting on this answer. {pills}</div></div>
            </div>''')

    # ---------- Source citations ----------
    if evidence:
        st.write("")
        render(section_header("📚", f"Source Citations ({len(evidence)} Grounded Evidence Chunks)"))
        full_docs = pd.concat([
            get_clinical_notes(patient_id).rename(columns={"note_id": "doc_id"})[["doc_id", "raw_text"]],
            get_discharge_summaries(patient_id).rename(columns={"summary_id": "doc_id"})[["doc_id", "raw_text"]],
            run_query("SELECT FILING_ID AS DOC_ID, RAW_TEXT FROM REGULATORY_FILINGS WHERE PATIENT_ID = %s", [patient_id]),
        ], ignore_index=True)
        for item in evidence:
            score = item.get("relevance_score", 0)
            pct = score / len(keywords) * 100 if keywords else 0
            cls = "risk-low" if pct >= 60 else "risk-medium" if pct >= 30 else "risk-high"
            render(f'''
            <div class="citation-card">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-weight:600;color:#0037B0;" class="mono">[Doc #{esc(item["doc_id"])} §{esc(item["section"])}]</span>
                <span class="{cls}">Match: {score}/{len(keywords)} keywords</span>
              </div>
              <div class="grid-2" style="gap:4px;font-size:12px;color:#434655;margin-top:6px;">
                <div><strong>Type:</strong> {esc(item["doc_type"])}</div>
                <div><strong>Section:</strong> {esc(item["section"])}</div>
                <div><strong>Patient:</strong> {esc(patient_id)}</div>
                <div><strong>Source:</strong> Snowflake · HCLS_PATIENT360</div>
              </div>
              <div class="chunk"><div class="eyebrow">Exact extracted raw chunk</div><p>"{esc(item["excerpt"])}"</p></div>
              <div style="font-size:11px;color:#434655;margin-top:8px;" class="mono">🔗 SHA-256: {sha256(item["excerpt"])[:32]}…</div>
            </div>''')
            match = full_docs[full_docs["doc_id"] == item["doc_id"]]
            with st.expander("Inspect full document", icon=":material/open_in_new:"):
                st.text(match.iloc[0]["raw_text"] if not match.empty else "Full document not available.")

    # ---------- Audit footer ----------
    cited_note = f"Q: {question}\n\n{answer}\n\nSources: " + ", ".join(f"{e['doc_id']} ({e['section']})" for e in evidence)
    st.write("")
    fcol, c1, c2 = st.columns([4, 1.2, 1.2], vertical_alignment="center")
    with fcol:
        render('<div class="audit-footer" style="border-top:none;margin:0;padding:0;"><span>⚖️</span>'
               '<span>AUDIT NOTICE: All generated answers are strictly grounded in synthetic EHR source files.</span></div>')
    with c1.popover("Copy Cited Note", icon=":material/content_copy:", width="stretch"):
        st.caption("Use the copy icon at the top-right of the block.")
        st.code(cited_note, language=None, wrap_lines=True)
    if c2.button(":material/playlist_add: Add to Care Plan", type="primary", width="stretch"):
        st.session_state.setdefault("care_plan", []).append({"patient_id": patient_id, "note": cited_note})
        log_audit_event("ADD_TO_CARE_PLAN", patient_id=patient_id,
                        details={"question": question, "execution_id": exec_id,
                                 "sources": [e["doc_id"] for e in evidence]})
        st.toast("Cited note added to care plan and logged to audit trail.", icon=":material/check_circle:")

# ---------- Patient documents ----------
st.write("")
render(section_header("🗒️", "Patient Documents"))
with st.container(key="card_documents"):
    tab_notes, tab_summaries = st.tabs([":material/description: Clinical notes", ":material/assignment: Discharge summaries"])
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
