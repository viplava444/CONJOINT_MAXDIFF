"""
ui/config_panel.py
------------------
Step 1: Configure study inputs.
  - CBC: attribute/level editor, design settings, prohibitions
  - MaxDiff: item list editor, set settings
"""

from __future__ import annotations

from typing import Dict, List

import streamlit as st

from config.settings import PRESET_ATTRIBUTES, PRESET_MAXDIFF_ITEMS, CBC_DEFAULTS, MAXDIFF_DEFAULTS
from utils.helpers import SessionKeys


# ── CBC Attribute Editor ──────────────────────────────────────────────────────

def _render_attribute_editor() -> None:
    """Editable list of attributes and their levels."""
    attrs: List[Dict] = st.session_state[SessionKeys.ATTRIBUTES]

    for i, attr in enumerate(attrs):
        with st.container():
            col_name, col_price, col_del = st.columns([3, 1, 0.5])
            with col_name:
                new_name = st.text_input(
                    "Attribute name", value=attr["name"],
                    key=f"attr_name_{i}", label_visibility="collapsed",
                    placeholder="Attribute name"
                )
                attrs[i]["name"] = new_name

            with col_price:
                attrs[i]["is_price"] = st.checkbox(
                    "Price attr", value=attr.get("is_price", False),
                    key=f"attr_price_{i}",
                    help="Mark if this attribute is a price/cost variable (affects Bayesian priors)"
                )

            with col_del:
                if st.button("✕", key=f"del_attr_{i}", help="Remove attribute",
                             use_container_width=True):
                    attrs.pop(i)
                    st.session_state[SessionKeys.ATTRIBUTES] = attrs
                    st.rerun()

            # Levels as a comma-separated text input
            levels_str = ", ".join(attr["levels"])
            new_levels_str = st.text_input(
                "Levels (comma-separated)", value=levels_str,
                key=f"attr_levels_{i}",
                placeholder="e.g. Sony, Samsung, LG",
                help="Enter levels separated by commas. Minimum 2 levels required."
            )
            attrs[i]["levels"] = [lvl.strip() for lvl in new_levels_str.split(",") if lvl.strip()]

            n_levels = len(attrs[i]["levels"])
            if n_levels < 2:
                st.warning(f"⚠ At least 2 levels required.", icon=None)
            else:
                st.caption(f"{n_levels} levels · {n_levels - 1} parameters")
            st.divider()

    st.session_state[SessionKeys.ATTRIBUTES] = attrs


def _render_prohibitions() -> None:
    """Add/remove prohibited attribute-level combinations."""
    attrs: List[Dict] = st.session_state[SessionKeys.ATTRIBUTES]
    prohibitions: List[Dict] = st.session_state[SessionKeys.PROHIBITIONS]

    if not attrs:
        st.info("Add attributes first to define prohibitions.")
        return

    attr_names = [a["name"] for a in attrs]

    # Display existing prohibitions
    if prohibitions:
        for i, p in enumerate(prohibitions):
            col_text, col_del = st.columns([5, 1])
            with col_text:
                st.markdown(
                    f'<div style="padding:6px 10px;background:#FEF3C7;border-radius:6px;'
                    f'font-size:13px"><b>{p["attribute_a"]}</b> = {p["level_a"]} '
                    f'&nbsp;✕&nbsp; <b>{p["attribute_b"]}</b> = {p["level_b"]}</div>',
                    unsafe_allow_html=True
                )
            with col_del:
                if st.button("✕", key=f"del_prohib_{i}"):
                    prohibitions.pop(i)
                    st.session_state[SessionKeys.PROHIBITIONS] = prohibitions
                    st.rerun()
        st.write("")

    # Add new prohibition
    with st.expander("+ Add prohibition", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            attr_a = st.selectbox("Attribute A", attr_names, key="prohib_attr_a")
            level_a_options = next((a["levels"] for a in attrs if a["name"] == attr_a), [])
            level_a = st.selectbox("Level of A", level_a_options, key="prohib_level_a")
        with col2:
            remaining = [n for n in attr_names if n != attr_a]
            attr_b = st.selectbox("Attribute B", remaining if remaining else attr_names,
                                  key="prohib_attr_b")
            level_b_options = next((a["levels"] for a in attrs if a["name"] == attr_b), [])
            level_b = st.selectbox("Level of B", level_b_options, key="prohib_level_b")

        if st.button("Add prohibition", type="secondary"):
            prohibitions.append({
                "attribute_a": attr_a, "level_a": level_a,
                "attribute_b": attr_b, "level_b": level_b,
            })
            st.session_state[SessionKeys.PROHIBITIONS] = prohibitions
            st.rerun()

    st.session_state[SessionKeys.PROHIBITIONS] = prohibitions


# ── MaxDiff Item Editor ───────────────────────────────────────────────────────

def _render_item_editor() -> None:
    """Editable numbered list of MaxDiff items."""
    items: List[str] = st.session_state[SessionKeys.ITEMS]

    for i, item in enumerate(items):
        col_num, col_text, col_del = st.columns([0.4, 5, 0.5])
        with col_num:
            st.markdown(
                f'<div style="padding:8px 0;color:#6B7280;font-size:13px">{i+1}.</div>',
                unsafe_allow_html=True
            )
        with col_text:
            items[i] = st.text_input(
                f"Item {i+1}", value=item,
                key=f"md_item_{i}", label_visibility="collapsed",
                placeholder=f"Item {i+1}"
            )
        with col_del:
            if st.button("✕", key=f"del_item_{i}") and len(items) > 4:
                items.pop(i)
                st.session_state[SessionKeys.ITEMS] = items
                st.rerun()

    st.session_state[SessionKeys.ITEMS] = items


# ── Main render function ──────────────────────────────────────────────────────

def render_config_panel() -> None:
    """Render the full configuration panel (Step 1)."""
    study_type = st.session_state[SessionKeys.STUDY_TYPE]

    # ── Preset loader ──
    st.subheader("Quick start with a preset")
    preset_dict = PRESET_ATTRIBUTES if study_type == "CBC" else PRESET_MAXDIFF_ITEMS
    preset_names = list(preset_dict.keys())
    selected_preset = st.selectbox("Load preset", ["— Choose preset —"] + preset_names,
                                   label_visibility="collapsed")
    if selected_preset != "— Choose preset —" and selected_preset != "Custom":
        if st.button(f"Load '{selected_preset}' preset"):
            if study_type == "CBC":
                st.session_state[SessionKeys.ATTRIBUTES] = [
                    dict(a) for a in preset_dict[selected_preset]
                ]
                st.session_state[SessionKeys.PROHIBITIONS] = []
            else:
                st.session_state[SessionKeys.ITEMS] = list(preset_dict[selected_preset])
            st.rerun()

    st.divider()

    if study_type == "CBC":
        _render_cbc_config()
    else:
        _render_maxdiff_config()


def _render_cbc_config() -> None:
    """CBC-specific configuration panels."""

    # ── Attributes ──
    st.subheader("Attributes & levels")
    st.caption("Each attribute needs at least 2 levels. Use comma separation for levels.")

    _render_attribute_editor()

    col_add, col_summary = st.columns([1, 2])
    with col_add:
        if st.button("+ Add attribute", use_container_width=True):
            attrs = st.session_state[SessionKeys.ATTRIBUTES]
            attrs.append({
                "name": f"Attribute {len(attrs) + 1}",
                "levels": ["Level 1", "Level 2", "Level 3"],
                "is_price": False,
            })
            st.session_state[SessionKeys.ATTRIBUTES] = attrs
            st.rerun()

    with col_summary:
        attrs = st.session_state[SessionKeys.ATTRIBUTES]
        if attrs:
            valid_attrs = [a for a in attrs if len(a["levels"]) >= 2]
            total_levels = sum(len(a["levels"]) for a in valid_attrs)
            n_params = sum(len(a["levels"]) - 1 for a in valid_attrs)
            full_factorial = 1
            for a in valid_attrs:
                full_factorial *= len(a["levels"])
            st.info(
                f"**{len(valid_attrs)} attributes** · "
                f"**{total_levels} total levels** · "
                f"**{n_params} parameters** · "
                f"Full factorial: {full_factorial:,} profiles"
            )

    st.divider()

    # ── Design settings ──
    st.subheader("Design settings")
    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Tasks per respondent", min_value=4, max_value=30,
                        value=CBC_DEFAULTS["n_tasks"], key="cbc_n_tasks",
                        help="8–12 is typical for CBC. More tasks = better estimation but more fatigue.")
        st.number_input("Alternatives per task", min_value=2, max_value=5,
                        value=CBC_DEFAULTS["n_alternatives"], key="cbc_n_alts",
                        help="2–4 alternatives per task. 3 is the most common.")
        st.number_input("Survey blocks (versions)", min_value=1, max_value=20,
                        value=CBC_DEFAULTS["n_blocks"], key="cbc_n_blocks",
                        help="Number of different task orderings. Reduces order effects across respondents.")
        st.number_input("Expected sample size", min_value=30, max_value=10000,
                        value=CBC_DEFAULTS["sample_size"], key="cbc_sample_size",
                        help="Used for SE estimates. Does not affect design generation.")

    with col2:
        st.number_input("Holdout tasks", min_value=0, max_value=6,
                        value=CBC_DEFAULTS["n_holdout"], key="cbc_n_holdout",
                        help="Extra tasks for model validation (not used in estimation).")
        st.checkbox("Include 'None' option", value=CBC_DEFAULTS["include_none"],
                    key="cbc_include_none",
                    help="Adds a 'None of these' alternative to each task.")
        st.checkbox("Include holdout tasks", value=CBC_DEFAULTS["include_holdout"],
                    key="cbc_include_holdout")
        st.checkbox("Dual-response none",
                    value=CBC_DEFAULTS["dual_none"], key="cbc_dual_none",
                    help="Two-stage: first pick best, then 'would you buy any of these?'")
        st.checkbox("Bayesian D-efficiency", value=CBC_DEFAULTS["bayesian"],
                    key="cbc_bayesian",
                    help="Use Bayesian priors for D-efficiency (recommended). Slightly slower.")
        st.checkbox("Respondent fatigue optimization", value=CBC_DEFAULTS["fatigue_opt"],
                    key="cbc_fatigue_opt",
                    help="Reorder tasks so hardest tasks appear mid-survey (avoids fatigue effects).")

        st.number_input("Prior variance (σ²)", min_value=0.1, max_value=10.0,
                        value=float(CBC_DEFAULTS["prior_variance"]),
                        step=0.1, key="cbc_prior_variance",
                        help="Bayesian prior variance for β. Higher = broader priors. 1.0 is a sensible default.")

    st.divider()

    # ── Prohibitions ──
    st.subheader("Prohibited combinations")
    st.caption("Prevent logically impossible or commercially irrelevant level combinations.")
    _render_prohibitions()


def _render_maxdiff_config() -> None:
    """MaxDiff-specific configuration panels."""

    # ── Items ──
    st.subheader("Items list")
    st.caption("Minimum 4 items. Each item will appear in multiple sets.")

    _render_item_editor()

    col_add, col_summary = st.columns([1, 2])
    with col_add:
        if st.button("+ Add item", use_container_width=True):
            items = st.session_state[SessionKeys.ITEMS]
            items.append(f"Item {len(items) + 1}")
            st.session_state[SessionKeys.ITEMS] = items
            st.rerun()
    with col_summary:
        items = st.session_state[SessionKeys.ITEMS]
        valid_items = [i for i in items if i.strip()]
        k = st.session_state.get("md_per_set", MAXDIFF_DEFAULTS["n_per_set"])
        r = st.session_state.get("md_target_app", MAXDIFF_DEFAULTS["target_appearances"])
        import math
        n_sets = math.ceil(len(valid_items) * r / k) if valid_items and k > 0 else 0
        bibd_lambda = r * (k - 1) / (len(valid_items) - 1) if len(valid_items) > 1 else 0
        st.info(
            f"**{len(valid_items)} items** · "
            f"Sets required: **{n_sets}** · "
            f"BIBD λ: **{bibd_lambda:.2f}**"
        )

    st.divider()

    # ── MaxDiff settings ──
    st.subheader("MaxDiff settings")
    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Items per set", min_value=3, max_value=7,
                        value=MAXDIFF_DEFAULTS["n_per_set"], key="md_per_set",
                        help="4–5 items per set is typical. More items per set = fewer total sets.")
        st.number_input("Target appearances per item", min_value=2, max_value=8,
                        value=MAXDIFF_DEFAULTS["target_appearances"], key="md_target_app",
                        help="How many times each item should appear across all sets. 3–4 is standard.")
        st.number_input("Survey blocks", min_value=1, max_value=10,
                        value=MAXDIFF_DEFAULTS["n_blocks"], key="md_n_blocks")

    with col2:
        st.checkbox("Position balance", value=MAXDIFF_DEFAULTS["position_balance"],
                    key="md_pos_balance",
                    help="Ensure each item appears in each ordinal position equally often.")
        st.checkbox("Pair coverage optimization", value=MAXDIFF_DEFAULTS["pair_optimization"],
                    key="md_pair_opt",
                    help="Use swap heuristic to maximize the number of item pairs that co-appear.")
        st.checkbox("Anchored MaxDiff", value=MAXDIFF_DEFAULTS["anchored"],
                    key="md_anchored",
                    help="Adds a follow-up 'would you choose this?' question after each set.")
