"""
ui/export_panel.py
------------------
Step 5: Export the design in multiple formats.

Fix (2026-04-10): replaced deprecated use_container_width=True with
width='stretch' on all st.download_button calls.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from exports import (
    export_cbc_csv, export_cbc_excel, export_cbc_json,
    export_maxdiff_csv, export_maxdiff_excel, export_maxdiff_json,
    export_qualtrics_csv, export_sawtooth_csv,
)
from utils.helpers import SessionKeys


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def _render_cbc_exports(design, diagnostics) -> None:
    """CBC export buttons."""
    ts = _timestamp()

    st.subheader("Standard formats")
    col1, col2, col3 = st.columns(3)

    with col1:
        csv_data = export_cbc_csv(design)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"cbc_design_{ts}.csv",
            mime="text/csv",
            width="stretch",
            help="Flat CSV with one row per (block, task, alternative)",
        )

    with col2:
        excel_data = export_cbc_excel(design, diagnostics)
        st.download_button(
            label="📥 Download Excel",
            data=excel_data,
            file_name=f"cbc_design_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            help="Multi-sheet workbook: Design Matrix, Diagnostics, Codebook",
        )

    with col3:
        json_data = export_cbc_json(design)
        st.download_button(
            label="📥 Download JSON",
            data=json_data,
            file_name=f"cbc_design_{ts}.json",
            mime="application/json",
            width="stretch",
            help="Hierarchical JSON with full metadata",
        )

    st.divider()
    st.subheader("Platform-specific formats")
    col4, col5 = st.columns(2)

    with col4:
        st.markdown("**Qualtrics**")
        st.caption("Generates embedded data variable names formatted for Qualtrics loop & merge.")
        q_data = export_qualtrics_csv(design)
        st.download_button(
            label="📥 Export for Qualtrics",
            data=q_data,
            file_name=f"cbc_qualtrics_{ts}.csv",
            mime="text/csv",
            width="stretch",
        )

    with col5:
        st.markdown("**Sawtooth Software**")
        st.caption("Numeric level codes (1-indexed) compatible with Lighthouse Studio import.")
        ssi_data = export_sawtooth_csv(design)
        st.download_button(
            label="📥 Export for Sawtooth",
            data=ssi_data,
            file_name=f"cbc_sawtooth_{ts}.csv",
            mime="text/csv",
            width="stretch",
        )

    st.divider()
    st.subheader("CSV preview (first 20 rows)")
    preview = export_cbc_csv(design).decode("utf-8")
    lines = preview.split("\n")[:21]
    st.code("\n".join(lines), language="text")


def _render_maxdiff_exports(design, diagnostics) -> None:
    """MaxDiff export buttons."""
    ts = _timestamp()

    st.subheader("Standard formats")
    col1, col2, col3 = st.columns(3)

    with col1:
        csv_data = export_maxdiff_csv(design)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"maxdiff_design_{ts}.csv",
            mime="text/csv",
            width="stretch",
        )

    with col2:
        excel_data = export_maxdiff_excel(design, diagnostics)
        st.download_button(
            label="📥 Download Excel",
            data=excel_data,
            file_name=f"maxdiff_design_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    with col3:
        json_data = export_maxdiff_json(design)
        st.download_button(
            label="📥 Download JSON",
            data=json_data,
            file_name=f"maxdiff_design_{ts}.json",
            mime="application/json",
            width="stretch",
        )

    st.divider()
    st.subheader("CSV preview (first 20 rows)")
    preview = export_maxdiff_csv(design).decode("utf-8")
    lines = preview.split("\n")[:21]
    st.code("\n".join(lines), language="text")


def render_export_panel() -> None:
    """Render the export panel (Step 5)."""
    study_type = st.session_state[SessionKeys.STUDY_TYPE]

    design = (
        st.session_state.get(SessionKeys.CBC_DESIGN)
        if study_type == "CBC"
        else st.session_state.get(SessionKeys.MAXDIFF_DESIGN)
    )
    diagnostics = (
        st.session_state.get(SessionKeys.CBC_DIAGNOSTICS)
        if study_type == "CBC"
        else st.session_state.get(SessionKeys.MAXDIFF_DIAGNOSTICS)
    )

    if design is None:
        st.info("Generate a design first (Step 2) before exporting.")
        return

    st.caption(
        "All exports include the full design across all blocks. "
        "Yellow-highlighted rows in Excel indicate holdout tasks."
    )
    st.divider()

    if study_type == "CBC":
        _render_cbc_exports(design, diagnostics)
    else:
        _render_maxdiff_exports(design, diagnostics)
