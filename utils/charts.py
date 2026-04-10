"""
utils/charts.py
---------------
Reusable Plotly chart builders for the diagnostics and preview panels.
All charts use the same color palette defined in config/settings.py.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from config.settings import CHART_COLORS
from core.models import DiagnosticsReport, LevelBalance


# ── Shared layout defaults ────────────────────────────────────────────────────

_BASE_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=10, r=10, t=30, b=10),
    showlegend=False,
)


# ── D-efficiency gauge ────────────────────────────────────────────────────────

def d_efficiency_gauge(d_eff: float) -> go.Figure:
    """Gauge chart showing D-efficiency with color zones."""
    color = (
        CHART_COLORS["success"] if d_eff >= 80
        else CHART_COLORS["warning"] if d_eff >= 65
        else CHART_COLORS["danger"]
    )
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(d_eff, 1),
        number={"suffix": "%", "font": {"size": 28}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 65],  "color": "#FEE2E2"},
                {"range": [65, 80], "color": "#FEF3C7"},
                {"range": [80, 100],"color": "#DCFCE7"},
            ],
            "threshold": {
                "line": {"color": color, "width": 3},
                "thickness": 0.75,
                "value": d_eff,
            },
        },
        title={"text": "D-Efficiency", "font": {"size": 13}},
    ))
    fig.update_layout(**_BASE_LAYOUT, height=200)
    return fig


# ── Level balance bar chart ───────────────────────────────────────────────────

def level_balance_chart(balance: List[LevelBalance]) -> go.Figure:
    """Grouped bar chart of level counts vs. expected for each attribute."""
    attrs = []
    levels = []
    counts = []
    expecteds = []
    colors = []

    for b in balance:
        for lvl, cnt in b.counts.items():
            attrs.append(b.attribute_name)
            levels.append(f"{b.attribute_name}: {lvl}")
            counts.append(cnt)
            expecteds.append(round(b.expected_count, 1))
            dev = abs(cnt - b.expected_count) / max(b.expected_count, 1)
            colors.append(
                CHART_COLORS["success"] if dev <= 0.10
                else CHART_COLORS["warning"] if dev <= 0.20
                else CHART_COLORS["danger"]
            )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=levels,
        y=counts,
        name="Actual",
        marker_color=colors,
        text=[str(c) for c in counts],
        textposition="outside",
    ))
    fig.add_trace(go.Scatter(
        x=levels,
        y=expecteds,
        name="Expected",
        mode="markers",
        marker=dict(symbol="line-ew", size=14, color=CHART_COLORS["neutral"],
                    line=dict(width=2, color=CHART_COLORS["neutral"])),
    ))
    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Level frequency vs. expected", font=dict(size=13)),
        showlegend=True,
        legend=dict(orientation="h", y=1.1, x=0),
        xaxis=dict(tickangle=-35, tickfont=dict(size=10)),
        yaxis=dict(title="Count"),
        height=320,
        bargap=0.3,
    )
    return fig


# ── Correlation heatmap ───────────────────────────────────────────────────────

def correlation_heatmap(corr_matrix: pd.DataFrame) -> Optional[go.Figure]:
    """Heatmap of Spearman correlations between attributes."""
    if corr_matrix.empty:
        return None

    z = corr_matrix.values
    labels = list(corr_matrix.columns)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=labels,
        y=labels,
        colorscale=[
            [0.0, CHART_COLORS["danger"]],
            [0.5, "#FFFFFF"],
            [1.0, CHART_COLORS["primary"]],
        ],
        zmin=-1, zmax=1,
        text=np.round(z, 3),
        texttemplate="%{text}",
        textfont=dict(size=11),
        showscale=True,
        colorbar=dict(thickness=12, len=0.8),
    ))
    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Spearman attribute correlation matrix", font=dict(size=13)),
        height=max(200, 60 * len(labels) + 60),
        xaxis=dict(tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=11)),
    )
    return fig


# ── Item appearances bar (MaxDiff) ────────────────────────────────────────────

def item_appearances_chart(appearance_counts: Dict[str, int], target: int) -> go.Figure:
    """Horizontal bar chart of MaxDiff item appearance counts."""
    items = list(appearance_counts.keys())
    counts = [appearance_counts[i] for i in items]
    colors = [
        CHART_COLORS["success"] if abs(c - target) <= 1
        else CHART_COLORS["warning"] if abs(c - target) <= 2
        else CHART_COLORS["danger"]
        for c in counts
    ]

    fig = go.Figure(go.Bar(
        y=items,
        x=counts,
        orientation="h",
        marker_color=colors,
        text=counts,
        textposition="outside",
    ))
    fig.add_vline(
        x=target, line_dash="dash",
        line_color=CHART_COLORS["neutral"],
        annotation_text=f"Target: {target}",
        annotation_position="top right",
    )
    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Item appearance counts", font=dict(size=13)),
        height=max(200, 28 * len(items) + 60),
        xaxis=dict(title="Appearances"),
        yaxis=dict(tickfont=dict(size=10)),
        margin=dict(l=20, r=40, t=40, b=20),
    )
    return fig


# ── Complexity distribution (CBC) ─────────────────────────────────────────────

def task_complexity_chart(design) -> go.Figure:
    """Bar chart of complexity scores across tasks (for fatigue analysis)."""
    tasks = [t for t in design.tasks if not t.is_holdout and t.block == design.blocks[0]]
    task_nums = [t.task_number for t in tasks]
    scores = [t.complexity_score for t in tasks]

    fig = go.Figure(go.Bar(
        x=[f"T{n}" for n in task_nums],
        y=scores,
        marker_color=[
            CHART_COLORS["success"] if s <= np.percentile(scores, 33)
            else CHART_COLORS["warning"] if s <= np.percentile(scores, 66)
            else CHART_COLORS["danger"]
            for s in scores
        ],
    ))
    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Task complexity (fatigue optimization view)", font=dict(size=13)),
        xaxis=dict(title="Task"),
        yaxis=dict(title="Complexity score"),
        height=220,
    )
    return fig
