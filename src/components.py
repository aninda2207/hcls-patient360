"""Reusable HTML building blocks rendered with st.html (same DOM as the app, so styles.css applies).

All data values are HTML-escaped. Interactivity (buttons, inputs) stays in native Streamlit widgets.
"""
import hashlib
import html as _html
import json

import pandas as pd
import streamlit as st

TIER_TEXT = {"HIGH": "#BA1A1A", "MEDIUM": "#B45309", "LOW": "#047857"}
PRIORITY_CLASS = {"Urgent": "urgent", "High": "high", "Medium": "medium", "Low": "low"}
PRIORITY_BADGE = {"Urgent": "urgent", "High": "high", "Medium": "medium", "Low": "low"}
PRIORITY_WINDOW = {"Urgent": "24-48h", "High": "7-Day", "Medium": "30-Day", "Low": "90-Day"}
LACE_MAX = 30  # synthetic cohort's LACE scale (observed max 30)


def esc(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return _html.escape(str(v))


def render(markup):
    st.html(markup)


def sha256(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def risk_badge(tier):
    t = str(tier or "").upper()
    cls = {"HIGH": "risk-high", "MEDIUM": "risk-medium", "LOW": "risk-low",
           "URGENT": "risk-urgent"}.get(t, "risk-neutral")
    return f'<span class="{cls}">{esc(tier)}</span>'


def severity_badge(sev):
    cls = {"High": "risk-high", "Medium": "risk-medium", "Low": "risk-low"}.get(sev, "risk-neutral")
    return f'<span class="{cls}">{esc(sev)}</span>'


def citation_pill(label):
    return f'<span class="citation-pill">[{esc(label)}]</span>'


def status_pills(items):
    pills = "".join(f'<span class="status-pill"><span class="dot"></span>{esc(i)}</span>' for i in items)
    return f'<div class="status-row">{pills}</div>'


def page_title(title, subtitle=None):
    sub = f'<div class="page-sub">{esc(subtitle)}</div>' if subtitle else ""
    return f'<div class="page-title">{esc(title)}</div>{sub}'


def section_header(icon, title, subtitle=None, icon_bg="#E5EEFF"):
    sub = f'<div class="s">{esc(subtitle)}</div>' if subtitle else ""
    return (f'<div class="section-header"><div class="section-header-icon" style="background:{icon_bg};">{icon}</div>'
            f'<div><div class="t">{esc(title)}</div>{sub}</div></div>')


def metric_card(label, value, subtext, icon, color, progress_pct):
    pct = max(0, min(100, float(progress_pct or 0)))
    return f'''
    <div class="metric-card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:11px;color:#64748B;text-transform:uppercase;font-weight:600;letter-spacing:0.04em;">{esc(label)}</span>
        <span style="color:{color};font-size:20px;">{icon}</span>
      </div>
      <div style="margin:8px 0;">
        <div class="mono" style="font-size:28px;font-weight:600;color:#0B1C30;">{esc(value)}</div>
        <div style="font-size:12px;color:#64748B;">{esc(subtext)}</div>
      </div>
      <div style="width:100%;height:4px;background:#E5EEFF;border-radius:2px;overflow:hidden;">
        <div style="height:100%;background:{color};width:{pct:.0f}%;border-radius:2px;"></div>
      </div>
    </div>'''


def demo_card(label, value):
    return f'<div class="demo-card"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div></div>'


def initials(first, last):
    return (str(first or "?")[:1] + str(last or "")[:1]).upper()


def patient_header(patient, extra_pills="", subline=None):
    name = f"{patient.get('first_name', '')} {patient.get('last_name', '')}"
    tier = patient.get("risk_tier", "LOW")
    demographics = subline or " · ".join(
        esc(v) for v in [f"{patient.get('age')} y", patient.get("gender"), patient.get("ethnicity"),
                         patient.get("region"), patient.get("insurance_type")] if v)
    lace_color = TIER_TEXT.get(tier, "#0B1C30")
    pills = extra_pills or (
        f'<span class="score-pill">LACE: <strong style="color:{lace_color};">{esc(patient.get("lace_score"))}</strong>/{LACE_MAX}</span>'
        f'<span class="score-pill">Charlson: <strong>{esc(patient.get("charlson_index"))}</strong></span>'
        f'<span class="score-pill">Active Dx: <strong>{count_items(patient.get("active_diagnoses"))}</strong></span>'
    )
    return f'''
    <div class="card-container" style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;">
      <div style="display:flex;align-items:center;gap:16px;">
        <div style="width:64px;height:64px;border-radius:12px;background:#DCE9FF;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:#0037B0;">{esc(initials(patient.get('first_name'), patient.get('last_name')))}</div>
        <div>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <span style="font-size:24px;font-weight:700;color:#0B1C30;">{esc(name)}</span>
            {risk_badge(tier)}
            <span class="mono" style="font-size:12px;color:#434655;background:#E5EEFF;padding:2px 8px;border-radius:4px;">ID: {esc(patient.get('patient_id'))}</span>
          </div>
          <div style="font-size:13px;color:#434655;margin-top:4px;">{demographics}</div>
        </div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">{pills}</div>
    </div>'''


def gap_card(gap):
    sev = str(gap.get("severity", "Low"))
    return f'''
    <div class="gap-card {esc(sev.lower())}">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <div style="font-weight:600;color:#0B1C30;font-size:14px;">{esc(gap.get('gap_type'))}</div>{severity_badge(sev)}
      </div>
      <div style="font-size:13px;color:#434655;margin:6px 0;">{esc(gap.get('gap_description'))}</div>
      <div style="font-size:12px;color:#0B1C30;"><strong>Action:</strong> {esc(gap.get('recommended_action'))}</div>
      <div style="margin-top:6px;">{citation_pill(gap.get('evidence_source'))}</div>
    </div>'''


def action_card(rec, index):
    priority = rec.get("priority", "Medium")
    cls = PRIORITY_CLASS.get(priority, "medium")
    window = PRIORITY_WINDOW.get(priority, "30-Day")
    window_color = "#BA1A1A" if priority in ("Urgent", "High") else "#565E74"
    return f'''
    <div class="action-card {cls}">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
        <div>
          <div style="display:flex;gap:8px;margin-bottom:6px;"><span class="risk-{PRIORITY_BADGE.get(priority, 'neutral')}">{esc(priority)}</span>
            <span class="mono" style="font-size:11px;color:#64748B;">ACTION #{index:02d}</span></div>
          <div style="font-size:18px;font-weight:600;color:#0B1C30;">{esc(rec.get('action'))}</div>
        </div>
        <div style="text-align:right;">
          <div class="eyebrow">Window</div>
          <span class="mono" style="font-size:12px;color:{window_color};font-weight:600;">{window}</span>
        </div>
      </div>
      <div class="rationale">
        <div class="eyebrow">Clinical Rationale</div>
        <div style="font-size:13px;color:#0B1C30;">{esc(rec.get('rationale'))}</div>
        <div style="margin-top:8px;display:flex;gap:4px;flex-wrap:wrap;">{citation_pill(rec.get('evidence'))}</div>
      </div>
    </div>'''


def html_table(df, columns, badge_cols=(), num_cols=(), wrap_cols=(), max_height=440):
    """columns: list of (key, label). Renders a styled, scrollable HTML table."""
    head = "".join(f"<th>{esc(label)}</th>" for _, label in columns)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for key, _ in columns:
            v = r.get(key)
            if key in badge_cols:
                cells.append(f"<td>{risk_badge(v)}</td>")
            elif key in wrap_cols:
                if not isinstance(v, str):
                    v = json.dumps(v, default=str) if v is not None else None
                cells.append(f'<td class="wrap">{esc(v)}</td>')
            else:
                cells.append(f'<td class="{"num" if key in num_cols else ""}">{esc(v)}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<div class="table-wrap" style="max-height:{max_height}px;"><table class="data-table">'
            f'<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def count_items(val):
    if val is None:
        return 0
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return 0
    return len(val) if isinstance(val, list) else 0
