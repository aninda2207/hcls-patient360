import json


GAP_ACTIONS = {
    "Missing Screening": {
        "icon": ":material/labs:",
        "priority": "Schedule screening test",
    },
    "Medication Adherence": {
        "icon": ":material/medication:",
        "priority": "Medication reconciliation",
    },
    "Overdue Follow-up": {
        "icon": ":material/calendar_month:",
        "priority": "Schedule appointment",
    },
}


def prioritize_care_gaps(gaps_df):
    """Sort and annotate care gaps by clinical priority."""
    if gaps_df.empty:
        return []

    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_gaps = gaps_df.copy()
    sorted_gaps["_sort"] = sorted_gaps["severity"].map(severity_order).fillna(3)
    sorted_gaps = sorted_gaps.sort_values("_sort").drop(columns=["_sort"])

    actions = []
    for _, row in sorted_gaps.iterrows():
        gap_type = row["gap_type"]
        meta = GAP_ACTIONS.get(gap_type, {"icon": ":material/info:", "priority": "Review"})
        actions.append({
            "gap_type": gap_type,
            "description": row["gap_description"],
            "severity": row["severity"],
            "action": row["recommended_action"],
            "evidence": row["evidence_source"],
            "icon": meta["icon"],
            "priority_label": meta["priority"],
        })
    return actions


def generate_care_recommendations(patient_row, gaps_df):
    """Generate next-best-action recommendations for a patient."""
    recommendations = []
    risk_tier = patient_row.get("risk_tier", "LOW")

    if risk_tier == "HIGH":
        recommendations.append({
            "action": "Urgent Care Coordination Review",
            "rationale": f"Patient is in HIGH risk tier (LACE={patient_row.get('lace_score', 'N/A')}). "
                         f"Multidisciplinary team review recommended within 48 hours.",
            "evidence": "CMS: Hospital Readmissions Reduction Program",
            "priority": "Urgent",
        })

    prioritized = prioritize_care_gaps(gaps_df)
    for gap in prioritized[:5]:
        recommendations.append({
            "action": gap["action"],
            "rationale": gap["description"],
            "evidence": gap["evidence"],
            "priority": gap["severity"],
        })

    active_meds = patient_row.get("active_medications")
    if active_meds:
        if isinstance(active_meds, str):
            try:
                active_meds = json.loads(active_meds)
            except (json.JSONDecodeError, TypeError):
                active_meds = []
        if len(active_meds) >= 5:
            recommendations.append({
                "action": "Polypharmacy Review",
                "rationale": f"Patient is on {len(active_meds)} active medications. "
                             f"Review for drug interactions and simplification opportunities.",
                "evidence": "AGS Beers Criteria / STOPP-START Criteria",
                "priority": "Medium",
            })

    return recommendations
