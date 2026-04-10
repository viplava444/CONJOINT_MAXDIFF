"""
ui/diagnostics_panel.py
------------------------
Step 4: Statistical diagnostics report.
  - D-efficiency gauge
  - Level balance charts
  - Attribute correlation heatmap
  - Warnings and recommendations
  - Task complexity distribution (CBC)
  - Item appearance chart (MaxDiff)
"""

from __future__ import annotations

import streamlit as st

from core.models import DiagnosticsReport
from utils.charts import (
    d_efficiency_gauge, level_balance_chart, correlation_heatmap,
    item_appearances_chart, task_complexity_chart,
)
from utils.helpers import SessionKeys, efficiency_badge
from config.settings import D_EFFICIENCY_GOOD, D_EFFICIENCY_WARN, MAX_ATTR_CORRELATION


def _render_summary_metrics(report: DiagnosticsReport) -> None:
    """Four top-level KPI cards."""
    cols = st.columns(4)

    with cols[0]:
        d_color = (
            "normal" if report.d_efficiency >= D_EFFICIENCY_GOOD
            else "off" if report.d_efficiency >= D_EFFICIENCY_WARN
            else "inverse"
        )
        st.metric(
            label="D-Efficiency",
            value=f"{report.d_efficiency:.1f}%",
            delta=report.overall_grade,
            delta_color=d_color,
        )

    with cols[1]:
        if report.study_type == "CBC":
            corr_ok = report.max_attr_correlation < MAX_ATTR_CORRELATION
            st.metric(
                label="Max attr. correlation",
                value=f"{report.max_attr_correlation:.4f}",
                delta="✓ Independent" if corr_ok else "⚠ Correlated",
                delta_color="normal" if corr_ok else "inverse",
            )
        else:
            st.metric(
                label="Appearance variance",
                value=f"{report.appearance_variance:.3f}",
                delta="Lower is better",
                delta_color="off",
            )

    with cols[2]:
        if report.study_type == "CBC":
            overlap_ok = report.overlap_pct < 30
            st.metric(
                label="Task overlap",
                value=f"{report.overlap_pct:.1f}%",
                delta="✓ OK" if overlap_ok else "⚠ High",
                delta_color="normal" if overlap_ok else "inverse",
            )
        else:
            pair_ok = report.pair_coverage_pct >= 80
            st.metric(
                label="Pair coverage",
                value=f"{report.pair_coverage_pct:.1f}%",
                delta="✓ Good" if pair_ok else "⚠ Low",
                delta_color="normal" if pair_ok else "inverse",
            )

    with cols[3]:
        se_val = (
            f"{report.expected_se:.4f}"
            if report.expected_se == report.expected_se  # not NaN
            else "N/A"
        )
        st.metric(label="Expected SE / param", value=se_val)


def _render_warnings(report: DiagnosticsReport) -> None:
    """Display warnings and recommendations."""
    if not report.warnings and not report.recommendations:
        st.success("✓ No issues detected. The design meets all statistical quality thresholds.")
        return

    if report.warnings:
        for w in report.warnings:
            st.warning(f"⚠ {w}")

    if report.recommendations:
        with st.expander("Recommendations", expanded=True):
            for rec in report.recommendations:
                st.info(f"💡 {rec}")


def render_diagnostics_panel() -> None:
    """Render the full diagnostics panel (Step 4)."""
    study_type = st.session_state[SessionKeys.STUDY_TYPE]

    report: DiagnosticsReport = (
        st.session_state.get(SessionKeys.CBC_DIAGNOSTICS)
        if study_type == "CBC"
        else st.session_state.get(SessionKeys.MAXDIFF_DIAGNOSTICS)
    )
    design = (
        st.session_state.get(SessionKeys.CBC_DESIGN)
        if study_type == "CBC"
        else st.session_state.get(SessionKeys.MAXDIFF_DESIGN)
    )
    inp = (
        st.session_state.get(SessionKeys.CBC_INPUT)
        if study_type == "CBC"
        else st.session_state.get(SessionKeys.MAXDIFF_INPUT)
    )

    if report is None:
        st.info("Generate a design first (Step 2) to see diagnostics.")
        return

    # ── Summary KPIs ──
    st.subheader("Summary metrics")
    _render_summary_metrics(report)

    st.divider()

    # ── Warnings ──
    st.subheader("Quality assessment")
    _render_warnings(report)

    st.divider()

    # ── Charts ──
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader("D-Efficiency gauge")
        fig_gauge = d_efficiency_gauge(report.d_efficiency)
        st.plotly_chart(fig_gauge, use_container_width=True, key="gauge_chart")

    with col_right:
        if study_type == "CBC" and design is not None:
            st.subheader("Task complexity distribution")
            fig_complexity = task_complexity_chart(design)
            st.plotly_chart(fig_complexity, use_container_width=True, key="complexity_chart")
        elif study_type == "MaxDiff" and design is not None and inp is not None:
            st.subheader("Item appearance counts")
            fig_app = item_appearances_chart(design.appearance_counts, inp.target_appearances)
            st.plotly_chart(fig_app, use_container_width=True, key="app_chart")

    st.divider()

    # ── Level balance ──
    st.subheader("Level balance by attribute")
    if report.level_balance:
        fig_balance = level_balance_chart(report.level_balance)
        st.plotly_chart(fig_balance, use_container_width=True, key="balance_chart")

        # Also show table
        with st.expander("Level balance detail table"):
            rows = []
            for b in report.level_balance:
                for lvl, cnt in b.counts.items():
                    dev_pct = abs(cnt - b.expected_count) / max(b.expected_count, 1) * 100
                    rows.append({
                        "Attribute": b.attribute_name,
                        "Level": lvl,
                        "Count": cnt,
                        "Expected": round(b.expected_count, 1),
                        "Dev (%)": round(dev_pct, 1),
                        "Status": "✓" if dev_pct <= 10 else "⚠" if dev_pct <= 20 else "✗",
                    })
            import pandas as pd
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.divider()

    # ── Correlation matrix (CBC only) ──
    if study_type == "CBC" and not report.correlation_matrix.empty:
        st.subheader("Attribute independence")
        st.caption(
            "Values close to 0 indicate independence (good). "
            f"Threshold: |ρ| < {MAX_ATTR_CORRELATION}"
        )
        fig_corr = correlation_heatmap(report.correlation_matrix)
        if fig_corr:
            st.plotly_chart(fig_corr, use_container_width=True, key="corr_heatmap")

    # ── Design metadata ──
    with st.expander("Raw design metadata"):
        meta = {}
        if design is not None:
            meta = design.metadata
        st.json(meta)
