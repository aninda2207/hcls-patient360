import json

CHARLSON_WEIGHTS = {
    "E11.9": ("Diabetes without complications", 1),
    "I25.10": ("Coronary artery disease", 1),
    "I50.9": ("Heart failure", 1),
    "I48.0": ("Atrial fibrillation", 1),
    "N18.3": ("Chronic kidney disease Stage 3", 2),
    "J44.1": ("COPD with exacerbation", 1),
    "J45.20": ("Asthma", 1),
    "C34.90": ("Lung malignancy", 6),
    "G20": ("Parkinson disease", 0),
    "I10": ("Hypertension", 0),
    "F32.1": ("Depression", 0),
    "E66.01": ("Morbid obesity", 0),
    "E78.5": ("Hyperlipidemia", 0),
    "E03.9": ("Hypothyroidism", 0),
}


def explain_charlson(active_diagnoses):
    """Return a list of (condition, weight, icd10) contributing to the Charlson score."""
    if not active_diagnoses:
        return []
    if isinstance(active_diagnoses, str):
        try:
            active_diagnoses = json.loads(active_diagnoses)
        except (json.JSONDecodeError, TypeError):
            return []

    factors = []
    seen_codes = set()
    for dx in active_diagnoses:
        code = dx.get("code", "")
        if code in CHARLSON_WEIGHTS and code not in seen_codes:
            label, weight = CHARLSON_WEIGHTS[code]
            if weight > 0:
                factors.append({"condition": label, "weight": weight, "icd10": code})
                seen_codes.add(code)
    return sorted(factors, key=lambda x: -x["weight"])


def explain_lace(lace_score, charlson_index, patient_row):
    """Break down LACE score into its components with explanations."""
    components = []
    charlson_contrib = min(charlson_index, 7)
    remaining = lace_score - charlson_contrib

    components.append({
        "component": "C — Comorbidity (Charlson)",
        "score": charlson_contrib,
        "detail": f"Charlson Index = {charlson_index} (capped at 7 for LACE)"
    })

    if remaining >= 3:
        components.append({
            "component": "A — Acuity (Emergency admission)",
            "score": 3,
            "detail": "Patient had emergency encounter(s)"
        })
        remaining -= 3

    if remaining > 0:
        l_est = min(remaining, 7)
        components.append({
            "component": "L — Length of stay",
            "score": l_est,
            "detail": f"Longest inpatient stay scored {l_est} (max 7)"
        })
        remaining -= l_est

    if remaining > 0:
        components.append({
            "component": "E — ED visits (6 months)",
            "score": remaining,
            "detail": f"{remaining} ED visit(s) in past 6 months"
        })

    return components


def get_risk_summary(patient_row):
    """Generate a plain-text risk summary for a patient."""
    tier = patient_row.get("risk_tier", "Unknown")
    lace = patient_row.get("lace_score", 0)
    charlson = patient_row.get("charlson_index", 0)

    if tier == "HIGH":
        urgency = "Immediate attention required."
    elif tier == "MEDIUM":
        urgency = "Close monitoring recommended."
    else:
        urgency = "Routine follow-up appropriate."

    return (
        f"Risk Tier: {tier} | LACE Score: {lace} | Charlson Index: {charlson}. "
        f"{urgency}"
    )
