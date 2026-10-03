import json
from src.data_loader import run_query


def search_clinical_evidence(patient_id, question):
    """Search clinical notes and discharge summaries for evidence relevant to a question.
    Returns a list of cited evidence items with document references."""
    notes = run_query("""
        SELECT NOTE_ID AS DOC_ID, 'Clinical Note' AS DOC_TYPE, NOTE_TYPE AS SECTION,
               RAW_TEXT, PARSED_JSON
        FROM CLINICAL_NOTES
        WHERE PATIENT_ID = %s
        ORDER BY NOTE_ID DESC
    """, [patient_id])

    summaries = run_query("""
        SELECT SUMMARY_ID AS DOC_ID, 'Discharge Summary' AS DOC_TYPE, 'Full Summary' AS SECTION,
               RAW_TEXT, PARSED_JSON
        FROM DISCHARGE_SUMMARIES
        WHERE PATIENT_ID = %s
        ORDER BY SUMMARY_ID DESC
    """, [patient_id])

    filings = run_query("""
        SELECT FILING_ID AS DOC_ID, 'Regulatory Filing' AS DOC_TYPE, FILING_TYPE AS SECTION,
               RAW_TEXT, PARSED_JSON
        FROM REGULATORY_FILINGS
        WHERE PATIENT_ID = %s
        ORDER BY FILING_ID DESC
    """, [patient_id])

    import pandas as pd
    all_docs = pd.concat([notes, summaries, filings], ignore_index=True)
    if all_docs.empty:
        return []

    question_lower = question.lower()
    keywords = [w for w in question_lower.split() if len(w) > 3]

    results = []
    for _, row in all_docs.iterrows():
        text = str(row.get("raw_text", "")).lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            raw = str(row.get("raw_text", ""))
            excerpt = _extract_relevant_excerpt(raw, keywords)
            results.append({
                "doc_id": row["doc_id"],
                "doc_type": row["doc_type"],
                "section": row["section"],
                "relevance_score": score,
                "excerpt": excerpt,
                "parsed_data": row.get("parsed_json"),
            })

    results.sort(key=lambda x: -x["relevance_score"])
    return results[:5]


def _extract_relevant_excerpt(text, keywords, context_chars=200):
    """Extract the most relevant excerpt from a document around keyword matches."""
    text_lower = text.lower()
    best_pos = -1
    best_score = 0

    for i in range(0, len(text_lower) - 50, 20):
        window = text_lower[i:i + context_chars]
        score = sum(1 for kw in keywords if kw in window)
        if score > best_score:
            best_score = score
            best_pos = i

    if best_pos == -1:
        return text[:context_chars] + ("..." if len(text) > context_chars else "")

    start = max(0, best_pos - 20)
    end = min(len(text), best_pos + context_chars)
    excerpt = text[start:end].strip()
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."
    return excerpt


def format_cited_answer(question, evidence_items):
    """Format a cited answer from evidence items."""
    if not evidence_items:
        return "No relevant clinical documentation found for this patient related to the question."

    answer_parts = [f"**Question:** {question}\n"]
    answer_parts.append("**Evidence found:**\n")

    for i, item in enumerate(evidence_items, 1):
        answer_parts.append(
            f"**[{i}]** _{item['doc_type']}_ — {item['section']} "
            f"(Doc: `{item['doc_id']}`)\n"
        )
        answer_parts.append(f"> {item['excerpt']}\n")

    answer_parts.append(
        f"\n---\n*{len(evidence_items)} source document(s) cited. "
        f"All answers are traceable to the referenced documents.*"
    )
    return "\n".join(answer_parts)
