"""
utils/helpers.py
----------------
Miscellaneous helpers: session state management, input sanitisation,
and small utility functions used across multiple UI panels.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from core.models import Attribute, CBCInput, MaxDiffInput, Prohibition
from config.settings import CBC_DEFAULTS, MAXDIFF_DEFAULTS


# ── Session state keys ────────────────────────────────────────────────────────

class SessionKeys:
    """Centralised list of all st.session_state keys."""
    STUDY_TYPE = "study_type"
    ATTRIBUTES = "attributes"
    PROHIBITIONS = "prohibitions"
    ITEMS = "md_items"
    CBC_INPUT = "cbc_input"
    MAXDIFF_INPUT = "maxdiff_input"
    CBC_DESIGN = "cbc_design"
    MAXDIFF_DESIGN = "maxdiff_design"
    CBC_DIAGNOSTICS = "cbc_diagnostics"
    MAXDIFF_DIAGNOSTICS = "maxdiff_diagnostics"
    ACTIVE_BLOCK = "active_block"
    SEED = "rng_seed"


def init_session_state(default_attrs: List[Dict], default_items: List[str]) -> None:
    """
    Initialise all session state keys with sensible defaults.
    Call once at the top of app.py; idempotent.
    """
    defaults = {
        SessionKeys.STUDY_TYPE: "CBC",
        SessionKeys.ATTRIBUTES: default_attrs,
        SessionKeys.PROHIBITIONS: [],
        SessionKeys.ITEMS: default_items,
        SessionKeys.CBC_INPUT: None,
        SessionKeys.MAXDIFF_INPUT: None,
        SessionKeys.CBC_DESIGN: None,
        SessionKeys.MAXDIFF_DESIGN: None,
        SessionKeys.CBC_DIAGNOSTICS: None,
        SessionKeys.MAXDIFF_DIAGNOSTICS: None,
        SessionKeys.ACTIVE_BLOCK: 1,
        SessionKeys.SEED: 42,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ── Input builders ────────────────────────────────────────────────────────────

def build_cbc_input(
    attributes: List[Dict],
    prohibitions: List[Dict],
    n_tasks: int,
    n_alts: int,
    n_blocks: int,
    n_holdout: int,
    sample_size: int,
    include_none: bool,
    include_holdout: bool,
    dual_none: bool,
    bayesian: bool,
    prior_variance: float,
    fatigue_opt: bool,
) -> CBCInput:
    """Convert raw UI dicts into a typed CBCInput object."""
    attr_objects = [
        Attribute(
            name=a["name"],
            levels=[lvl.strip() for lvl in a["levels"] if lvl.strip()],
            is_price=a.get("is_price", False),
        )
        for a in attributes
        if a["name"].strip() and len(a["levels"]) >= 2
    ]

    prohib_objects = [
        Prohibition(
            attribute_a=p["attribute_a"],
            level_a=p["level_a"],
            attribute_b=p["attribute_b"],
            level_b=p["level_b"],
        )
        for p in prohibitions
        if all(p.get(k) for k in ["attribute_a", "level_a", "attribute_b", "level_b"])
    ]

    return CBCInput(
        attributes=attr_objects,
        n_tasks=n_tasks,
        n_alternatives=n_alts,
        n_blocks=n_blocks,
        n_holdout=n_holdout,
        sample_size=sample_size,
        include_none=include_none,
        include_holdout=include_holdout,
        dual_none=dual_none,
        bayesian=bayesian,
        prior_variance=prior_variance,
        fatigue_opt=fatigue_opt,
        prohibitions=prohib_objects,
    )


def build_maxdiff_input(
    items: List[str],
    n_per_set: int,
    target_appearances: int,
    n_blocks: int,
    position_balance: bool,
    pair_optimization: bool,
    anchored: bool,
) -> MaxDiffInput:
    """Convert raw UI values into a typed MaxDiffInput object."""
    clean_items = [i.strip() for i in items if i.strip()]
    return MaxDiffInput(
        items=clean_items,
        n_per_set=n_per_set,
        target_appearances=target_appearances,
        n_blocks=n_blocks,
        position_balance=position_balance,
        pair_optimization=pair_optimization,
        anchored=anchored,
    )


# ── Validation ────────────────────────────────────────────────────────────────

def validate_cbc_inputs(inp: CBCInput) -> List[str]:
    """Return a list of error messages; empty list means valid."""
    errors = []
    if len(inp.attributes) < 2:
        errors.append("At least 2 attributes are required.")
    for attr in inp.attributes:
        if attr.n_levels < 2:
            errors.append(f"Attribute '{attr.name}' needs at least 2 levels.")
    if inp.n_tasks < 4:
        errors.append("At least 4 tasks per respondent are required.")
    if inp.n_alternatives < 2:
        errors.append("At least 2 alternatives per task are required.")
    if inp.sample_size < 30:
        errors.append("Sample size should be at least 30.")

    # Check feasibility: design must not be over-constrained
    total_combos = inp.full_factorial_size
    needed = inp.n_tasks * inp.n_alternatives
    if needed > total_combos * 3:
        errors.append(
            f"Design has {total_combos} unique profiles but needs {needed} "
            f"task-alternative slots. Add more attributes or levels."
        )
    return errors


def validate_maxdiff_inputs(inp: MaxDiffInput) -> List[str]:
    errors = []
    if inp.n_items < 4:
        errors.append("At least 4 items are required for MaxDiff.")
    if inp.n_per_set < 3:
        errors.append("Minimum 3 items per set.")
    if inp.n_per_set > inp.n_items:
        errors.append("Items per set cannot exceed total number of items.")
    if inp.n_per_set >= inp.n_items:
        errors.append("Items per set must be less than total items.")
    return errors


# ── Formatting helpers ────────────────────────────────────────────────────────

def badge_html(text: str, kind: str = "info") -> str:
    """Return an HTML badge span. kind ∈ {success, warning, danger, info, neutral}."""
    colors = {
        "success": ("#DCFCE7", "#166534"),
        "warning": ("#FEF3C7", "#92400E"),
        "danger":  ("#FEE2E2", "#991B1B"),
        "info":    ("#DBEAFE", "#1E40AF"),
        "neutral": ("#F3F4F6", "#374151"),
    }
    bg, fg = colors.get(kind, colors["info"])
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:12px;font-size:11px;font-weight:600">{text}</span>'
    )


def efficiency_badge(d_eff: float) -> str:
    if d_eff >= 80:
        return badge_html(f"{d_eff:.1f}% Excellent", "success")
    elif d_eff >= 65:
        return badge_html(f"{d_eff:.1f}% Marginal", "warning")
    else:
        return badge_html(f"{d_eff:.1f}% Poor", "danger")


def metric_delta_color(value: float, threshold_good: float, higher_is_better: bool = True) -> str:
    """Return 'normal', 'inverse', or 'off' for st.metric delta_color."""
    if higher_is_better:
        return "normal" if value >= threshold_good else "inverse"
    else:
        return "normal" if value <= threshold_good else "inverse"
