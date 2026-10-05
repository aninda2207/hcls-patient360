import streamlit as st
import pathlib
import os
import tempfile
import json

st.set_page_config(page_title="Upload Document", page_icon=":material/upload_file:", layout="wide")

css_path = pathlib.Path(__file__).parent.parent / "static" / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from src.data_loader import run_query, get_connection

st.markdown("## :material/upload_file: Upload Clinical Document")
st.caption("Upload prescriptions, clinical notes, or discharge summaries for AI-powered extraction.")

patients = run_query("SELECT PATIENT_ID, FIRST_NAME, LAST_NAME FROM PATIENTS ORDER BY PATIENT_ID")
patient_options = {
    f"{r['patient_id']} — {r['first_name']} {r['last_name']}": r["patient_id"]
    for _, r in patients.iterrows()
}

selected = st.selectbox("Select a patient", options=list(patient_options.keys()), key="upload_patient")
if not selected:
    st.stop()

patient_id = patient_options[selected]

doc_type = st.selectbox(
    "Document Type",
    ["Prescription", "Clinical Note", "Discharge Summary", "Regulatory Filing", "Lab Report", "Other"],
    key="doc_type",
)

uploaded_file = st.file_uploader(
    "Upload document",
    type=["pdf", "png", "jpg", "jpeg", "txt", "docx"],
    key="file_uploader",
)

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    file_ext = os.path.splitext(uploaded_file.name)[1].lower()

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

    with st.expander("Document Preview", expanded=True):
        st.text(raw_text[:2000])

    if st.button(":material/auto_fix_high: Parse & Extract Data", use_container_width=True):
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
                cur.execute("""
                    INSERT INTO CLINICAL_NOTES (NOTE_ID, PATIENT_ID, NOTE_TYPE, RAW_TEXT, PARSED_JSON)
                    VALUES (%s, %s, %s, %s, PARSE_JSON(%s))
                """, [note_id, patient_id, doc_type, raw_text, json.dumps(parsed_data)])
            elif doc_type == "Discharge Summary":
                summary_id = f"DS{abs(hash(uploaded_file.name)) % 100000:05d}"
                cur.execute("""
                    INSERT INTO DISCHARGE_SUMMARIES (SUMMARY_ID, PATIENT_ID, RAW_TEXT, PARSED_JSON)
                    VALUES (%s, %s, %s, PARSE_JSON(%s))
                """, [summary_id, patient_id, raw_text, json.dumps(parsed_data)])
            elif doc_type == "Regulatory Filing":
                filing_id = f"RF{abs(hash(uploaded_file.name)) % 100000:05d}"
                cur.execute("""
                    INSERT INTO REGULATORY_FILINGS (FILING_ID, PATIENT_ID, FILING_TYPE, RAW_TEXT, PARSED_JSON)
                    VALUES (%s, %s, %s, %s, PARSE_JSON(%s))
                """, [filing_id, patient_id, "Uploaded Filing", raw_text, json.dumps(parsed_data)])

            from src.data_loader import log_audit_event
            log_audit_event("UPLOAD_DOCUMENT", patient_id=patient_id,
                            details={"doc_type": doc_type, "file_name": uploaded_file.name})

            st.success(f"Document parsed and saved! Keywords found: {', '.join(keywords) if keywords else 'None'}")
            st.json(parsed_data)

    try:
        os.unlink(tmp_path)
    except OSError:
        pass
