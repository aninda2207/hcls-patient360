from datetime import datetime, timezone

import streamlit as st

from src.care_gaps import generate_care_recommendations
from src.components import LACE_MAX, TIER_TEXT, action_card, esc, page_title, patient_header, render
from src.data_loader import get_all_patients, get_patient_care_gaps, get_patient_detail, log_audit_event, run_query
from src.risk_scoring import explain_lace, get_risk_summary
from src.ui import patient_options as build_options

patients = get_all_patients()
patient_options = build_options(patients)

render(page_title("Care Actions", "Next-best-action recommendations with evidence, explainability and sign-off"))

selected = st.selectbox("Select a patient", options=list(patient_options.keys()), key="action_patient")
if not selected:
    st.stop()

patient_id = patient_options[selected]
patient = get_patient_detail(patient_id)
if patient is None:
    st.error("Patient not found.")
    st.stop()

tier = patient.get("risk_tier", "LOW")
lace = patient.get("lace_score", 0)
gaps_df = get_patient_care_gaps(patient_id)
recommendations = generate_care_recommendations(patient, gaps_df)

if st.session_state.get("_last_actions_patient") != patient_id:
    log_audit_event("GENERATE_ACTIONS", patient_id=patient_id, details={"recommendation_count": len(recommendations)})
    st.session_state["_last_actions_patient"] = patient_id

if tier == "HIGH":
    render(f'''
    <div class="alert-banner">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <span style="color:#BA1A1A;font-size:20px;">⚠️</span>
        <span style="font-weight:600;">Clinical Alert: High Readmission Risk</span>
        <span style="font-size:13px;opacity:0.85;">{esc(get_risk_summary(patient))}</span>
      </div>
      <div class="mono" style="font-size:12px;font-weight:600;white-space:nowrap;"><span class="pulse-dot"></span>PRIORITY 1 ESCALATION</div>
    </div>''')

lace_color = TIER_TEXT.get(tier, "#0B1C30")
pills = (f'<span class="score-pill" style="padding:8px 12px;">LACE: <strong style="color:{lace_color};">{esc(lace)}</strong>/{LACE_MAX}</span>'
         f'<span class="score-pill" style="padding:8px 12px;">Charlson: <strong>{esc(patient.get("charlson_index"))}</strong> pts</span>'
         f'<span class="score-pill" style="padding:8px 12px;">Open Gaps: <strong>{len(gaps_df)}</strong></span>')
last_enc = patient.get("last_encounter")
render(patient_header(patient, extra_pills=pills, subline=(
    f'{esc(patient.get("age"))} y · {esc(patient.get("gender"))} · {esc(patient.get("region"))} · '
    f'{esc(patient.get("insurance_type"))} · Last encounter: {esc(last_enc)}')))
st.write("")

left, right = st.columns([8, 4], gap="medium")

# ---------- LEFT: action cards ----------
with left:
    if not recommendations:
        st.success("No outstanding care actions for this patient.", icon=":material/verified:")
    else:
        counts = {p: sum(1 for r in recommendations if r.get("priority", "Medium") == p)
                  for p in ("Urgent", "High", "Medium", "Low")}
        options = [f"All ({len(recommendations)})"] + [f"{p} ({c})" for p, c in counts.items() if c]
        choice = st.segmented_control("Urgency", options, default=options[0], key=f"urg_{patient_id}",
                                      label_visibility="collapsed") or options[0]
        wanted = None if choice.startswith("All") else choice.split(" (")[0]

        for i, rec in enumerate(recommendations, 1):
            if wanted and rec.get("priority", "Medium") != wanted:
                continue
            render(action_card(rec, i))
            bar = st.container(horizontal=True)
            if bar.button(":material/assignment_ind: Accept & Assign", key=f"acc_{patient_id}_{i}", type="primary"):
                log_audit_event("ACCEPT_ACTION", patient_id=patient_id,
                                details={"action": rec["action"], "priority": rec.get("priority")})
                st.toast(f"Accepted: {rec['action']}", icon=":material/check_circle:")
            if bar.button(":material/edit: Modify Action", key=f"mod_{patient_id}_{i}"):
                log_audit_event("MODIFY_ACTION", patient_id=patient_id, details={"action": rec["action"]})
                st.toast("Modification request logged.", icon=":material/edit:")
            st.write("")

# ---------- RIGHT: explainability + sign-off ----------
with right:
    comps = explain_lace(lace, patient.get("charlson_index", 0), patient)
    max_score = max([c["score"] for c in comps] + [1])
    colors = ["#BA1A1A", "#1D4ED8", "#565E74", "#0037B0"]
    bars = "".join(f'''
      <div class="shap-row"><div class="top"><span>{esc(c["component"])}</span>
        <span class="mono" style="color:{colors[i % 4]};font-weight:600;">+{esc(c["score"])} pts</span></div>
        <div class="track"><div class="bar" style="width:{c["score"] / max_score * 100:.0f}%;background:{colors[i % 4]};"></div></div>
        <div style="font-size:11px;color:#64748B;margin-top:2px;">{esc(c["detail"])}</div></div>'''
                   for i, c in enumerate(comps))
    render(f'''
    <div class="card-container">
      <div class="card-title">Risk Score Explainability</div>
      <div class="card-sub">LACE component contributions (Total: {esc(lace)}/{LACE_MAX})</div>
      {bars or '<div style="font-size:13px;">No components available.</div>'}
      <div style="background:#EFF4FF;padding:10px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;margin-top:12px;">
        <span style="font-weight:600;font-size:13px;">Calculated Risk Sum</span>
        <span class="mono" style="font-size:20px;font-weight:700;color:{lace_color};">{esc(lace)} / {LACE_MAX}</span>
      </div>
    </div>''')
    st.write("")

    with st.container(key="card_signoff"):
        render('<div class="card-title">Sign-off &amp; Audit Log</div><div class="card-sub">HIPAA · 21 CFR Part 11</div>')
        c1 = st.checkbox("Clinical appropriateness verified", key=f"so1_{patient_id}")
        c2 = st.checkbox("Drug safety alerts acknowledged", key=f"so2_{patient_id}")
        c3 = st.checkbox("Patient care plan consent obtained", key=f"so3_{patient_id}")

        @st.fragment(run_every="1s")
        def _practitioner():
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            render(f'''
            <div style="background:#EFF4FF;padding:12px;border-radius:8px;">
              <div style="font-size:11px;color:#565E74;text-transform:uppercase;">Logged Practitioner</div>
              <div class="mono" style="font-size:12px;color:#0037B0;">ID: care_coordinator</div>
              <div style="font-weight:600;color:#0B1C30;">Care Coordinator</div>
              <div class="mono" style="font-size:12px;color:#565E74;">Session: {esc(st.session_state.get("_session_id", "local"))}</div>
              <div class="mono" style="font-size:12px;color:#565E74;">Audit Stamp: {now} UTC</div>
            </div>''')

        _practitioner()
        all_checked = c1 and c2 and c3
        if st.button(":material/draw: Authorize & Execute All Recommended Orders", type="primary", width="stretch",
                     disabled=not (all_checked and recommendations), key=f"auth_{patient_id}"):
            log_audit_event("AUTHORIZE_ACTIONS", patient_id=patient_id,
                            details={"actions": [r["action"] for r in recommendations]})
            st.toast(f"{len(recommendations)} order(s) authorized and logged.", icon=":material/verified:")
        if not all_checked:
            st.caption("Complete all three checks to enable authorization.")

        feed = run_query("""
            SELECT TIMESTAMP, ACTION FROM AUDIT_LOG
            WHERE PATIENT_ID = %s ORDER BY TIMESTAMP DESC LIMIT 4
        """, [patient_id])
        items = "".join(f'''
          <div style="display:flex;gap:8px;padding:4px 0;"><span style="width:6px;height:6px;border-radius:50%;background:{"#0037B0" if j == 0 else "#565E74"};margin-top:7px;flex:none;"></span>
          <div><div style="font-weight:500;font-size:13px;">{esc(r["action"])}</div>
          <div class="mono" style="font-size:11px;color:#565E74;">{esc(str(r["timestamp"])[:19])} · AUDIT_LOG</div></div></div>'''
                        for j, (_, r) in enumerate(feed.iterrows())) or '<div style="font-size:12px;color:#64748B;">No events yet.</div>'
        render(f'<div class="eyebrow" style="margin-top:8px;">Recent Audit Event Log</div>{items}')
