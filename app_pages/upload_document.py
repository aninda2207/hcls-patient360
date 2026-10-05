import streamlit as st
import os
import tempfile
import json
import hashlib

from src.components import citation_pill, esc, page_title, render, section_header
from src.data_loader import run_query, get_connection, _bind
from src.ui import patient_options as build_options

render(page_title("Upload Document", "Upload prescriptions, clinical notes, or discharge summaries for extraction"))

patients = run_query("SELECT PATIENT_ID, FIRST_NAME, LAST_NAME FROM PATIENTS ORDER BY PATIENT_ID")
patient_options = build_options(patients, with_tier=False)

with st.container(key="card_upload"):
    render(section_header("📤", "Upload Clinical Document", "PDF, PNG, JPG, TXT, DOCX"))
    c1, c2 = st.columns(2)
    selected = c1.selectbox("Select a patient", options=list(patient_options.keys()), key="upload_patient")
    doc_type = c2.selectbox(
        "Document Type",
        ["Prescription", "Clinical Note", "Discharge Summary", "Regulatory Filing", "Lab Report", "Other"],
        key="doc_type",
    )
    uploaded_file = st.file_uploader(
        "Upload document",
        type=["pdf", "png", "jpg", "jpeg", "txt", "docx"],
        key="file_uploader",
    )

if not selected:
    st.stop()

patient_id = patient_options[selected]

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    file_hash = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
    method = {".txt": "Plain text", ".pdf": "pdfplumber", ".png": "Tesseract OCR", ".jpg": "Tesseract OCR",
              ".jpeg": "Tesseract OCR"}.get(file_ext, "Placeholder (no parser)")

    if file_ext == ".txt":
        with open(tmp_path, "r") as f:
            raw_text = f.read()
    elif file_ext in (".png", ".jpg", ".jpeg"):
        try:
            from PIL import Image
            import pytesseract
            image = Image.open(tmp_path)
            raw_text = pytesseract.image_to_string(image)
            st.info(f"OCR extracted {len(raw_text)} characters from image")
        except ImportError:
            raw_text = f"[Image file: {uploaded_file.name}] - Install pytesseract+Pillow for OCR."
            st.info("OCR libraries not available. Install pytesseract and Pillow for image text extraction.")
        except Exception as e:
            raw_text = f"[Image file: {uploaded_file.name}] - OCR failed: {e}"
            st.warning(f"OCR extraction failed: {e}")
    elif file_ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(tmp_path) as pdf:
                raw_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            st.info(f"PDF parsed: {len(pdf.pages)} page(s) extracted")
        except ImportError:
            raw_text = f"[PDF file: {uploaded_file.name}] - Install pdfplumber for PDF parsing."
            st.info("PDF library not available. Install pdfplumber for text extraction.")
        except Exception as e:
            raw_text = f"[PDF file: {uploaded_file.name}] - Parsing failed: {e}"
            st.warning(f"PDF parsing failed: {e}")
    else:
        raw_text = f"[File: {uploaded_file.name}] - Document parsing would extract text."
        st.info("Document upload detected. In production, document parser would extract text.")

    with st.expander("Document Preview", expanded=True, icon=":material/preview:"):
        st.text(raw_text[:2000])

    if st.button(":material/auto_fix_high: Parse & Extract Data", type="primary", width="stretch"):
        with st.spinner("Parsing document..."):
            parsed_data = {
                "doc_type": doc_type,
                "file_name": uploaded_file.name,
                "file_type": file_ext,
                "extracted_text": raw_text[:500],
                "keywords_found": [],
            }

            keywords = []
            text_lower = raw_text.lower()
            for kw in ["mg", "tablet", "capsule", "daily", "twice", "refill", "prescription",
                        "diagnosis", "diabetic", "hypertension", "asthma", "copd", "heart failure"]:
                if kw in text_lower:
                    keywords.append(kw)
            parsed_data["keywords_found"] = keywords

            conn = get_connection()
            cur = conn.cursor()
            cur.execute("USE DATABASE HCLS_PATIENT360")
            cur.execute("USE SCHEMA PUBLIC")

            if doc_type in ("Prescription", "Clinical Note", "Lab Report", "Other"):
                note_id = f"N{abs(hash(uploaded_file.name)) % 100000:05d}"
                sql, params = _bind("""
                    INSERT INTO CLINICAL_NOTES (NOTE_ID, PATIENT_ID, NOTE_TYPE, RAW_TEXT, PARSED_JSON)
                    SELECT %s, %s, %s, %s, PARSE_JSON(%s)
                """, [note_id, patient_id, doc_type, raw_text, json.dumps(parsed_data)])
                cur.execute(sql, params)
            elif doc_type == "Discharge Summary":
                summary_id = f"DS{abs(hash(uploaded_file.name)) % 100000:05d}"
                sql, params = _bind("""
                    INSERT INTO DISCHARGE_SUMMARIES (SUMMARY_ID, PATIENT_ID, RAW_TEXT, PARSED_JSON)
                    SELECT %s, %s, %s, PARSE_JSON(%s)
                """, [summary_id, patient_id, raw_text, json.dumps(parsed_data)])
                cur.execute(sql, params)
            elif doc_type == "Regulatory Filing":
                filing_id = f"RF{abs(hash(uploaded_file.name)) % 100000:05d}"
                sql, params = _bind("""
                    INSERT INTO REGULATORY_FILINGS (FILING_ID, PATIENT_ID, FILING_TYPE, RAW_TEXT, PARSED_JSON)
                    SELECT %s, %s, %s, %s, PARSE_JSON(%s)
                """, [filing_id, patient_id, "Uploaded Filing", raw_text, json.dumps(parsed_data)])
                cur.execute(sql, params)

            from src.data_loader import log_audit_event
            log_audit_event("UPLOAD_DOCUMENT", patient_id=patient_id,
                            details={"doc_type": doc_type, "file_name": uploaded_file.name})

            st.success(f"Document parsed and saved to Snowflake for {patient_id}.", icon=":material/check_circle:")
            kw_html = " ".join(f'<span class="risk-routine">{esc(k)}</span>' for k in keywords) or \
                '<span style="font-size:12px;color:#64748B;">No keywords detected</span>'
            render(f'''
            <div class="card-container">
              {section_header("🧾", "Parsed Output", f"{esc(uploaded_file.name)} · {esc(doc_type)}")}
              <pre style="background:#F8FAFC;padding:12px;border-radius:8px;font-family:var(--mono);font-size:12px;
                          white-space:pre-wrap;max-height:320px;overflow:auto;border:1px solid #E2E8F0;">{esc(json.dumps(parsed_data, indent=2))}</pre>
              <div class="eyebrow" style="margin-top:10px;">Keywords</div>
              <div style="display:flex;gap:4px;flex-wrap:wrap;">{kw_html}</div>
              <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
                <span class="confidence-badge">Extraction: {esc(method)}</span>
                <span class="confidence-badge">{len(raw_text)} chars</span>
                {citation_pill("SHA-256: " + file_hash[:24] + "…")}
              </div>
            </div>''')

    try:
        os.unlink(tmp_path)
    except OSError:
        pass
