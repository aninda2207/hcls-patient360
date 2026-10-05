"""Shared UI helpers so every page uses the same header, badges and pickers."""
import streamlit as st

TIER_COLORS = {"HIGH": "red", "MEDIUM": "orange", "LOW": "green"}
SEVERITY_COLORS = {"High": "red", "Medium": "orange", "Low": "green"}
PRIORITY_COLORS = {"Urgent": "red", "High": "orange", "Medium": "blue", "Low": "green"}

# Hex values for Altair charts, matched to the badge colors above
TIER_HEX = {"HIGH": "#DC2626", "MEDIUM": "#D97706", "LOW": "#059669"}


def page_header(title, subtitle=None, icon=None):
    prefix = f":material/{icon}: " if icon else ""
    st.markdown(f"## {prefix}{title}")
    if subtitle:
        st.caption(subtitle)


def badge(label, colors, icon=None):
    """Inline markdown badge, e.g. badge("HIGH", TIER_COLORS)."""
    label = str(label) if label is not None else "N/A"
    color = colors.get(label, "gray")
    icon_md = f":material/{icon}: " if icon else ""
    return f":{color}-badge[{icon_md}{label}]"


def patient_options(patients, with_tier=True):
    """Map display label -> patient_id, same label format used across pages."""
    return {
        (f"{r['patient_id']} — {r['first_name']} {r['last_name']} ({r['risk_tier']})" if with_tier
         else f"{r['patient_id']} — {r['first_name']} {r['last_name']}"): r["patient_id"]
        for _, r in patients.iterrows()
    }
