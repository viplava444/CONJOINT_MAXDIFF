"""
ui/preview_panel.py
--------------------
Step 3: Respondent-facing preview of the survey design.
  - CBC: shows tasks as the respondent would see them, with radio buttons
  - MaxDiff: shows best/worst sets
  - Block/version selector
  - Highlights holdout tasks and price attributes
"""

from __future__ import annotations

from typing import List

import streamlit as st

from core.models import CBCDesign, CBCTask, MaxDiffDesign, MaxDiffSet
from utils.helpers import SessionKeys


# ── CBC task renderer ─────────────────────────────────────────────────────────

_NONE_LABEL = "None of these"


def _render_cbc_task(task: CBCTask, include_none: bool, task_display_num: int) -> None:
    """Render one CBC choice task with a realistic survey appearance."""

    holdout_badge = (
        '<span style="background:#FEF3C7;color:#92400E;padding:2px 8px;'
        'border-radius:10px;font-size:11px;font-weight:600;margin-left:8px">HOLDOUT</span>'
        if task.is_holdout else ""
    )

    st.markdown(
        f'<div style="font-size:14px;font-weight:600;margin:0 0 10px">'
        f'Task {task_display_num}{holdout_badge}</div>',
        unsafe_allow_html=True
    )
    st.caption("Please choose the option you prefer most:")

    n_alts = len(task.alternatives)
    extra_col = 1 if include_none else 0
    cols = st.columns(n_alts + extra_col)

    for alt_idx, (alt, col) in enumerate(zip(task.alternatives, cols)):
        with col:
            # Card border
            st.markdown(
                f'<div style="border:1px solid #E5E7EB;border-radius:10px;'
                f'padding:12px 14px;min-height:160px;background:#FAFAFA">',
                unsafe_allow_html=True
            )
            st.markdown(
                f'<div style="font-size:12px;font-weight:700;color:#6B7280;'
                f'margin-bottom:8px;text-transform:uppercase;letter-spacing:0.05em">'
                f'Option {alt_idx + 1}</div>',
                unsafe_allow_html=True
            )
            for attr_name, level_val in alt.items():
                # Detect price attribute by value heuristics (starts with $ or €)
                is_price = str(level_val).startswith(("$", "€", "£", "¥"))
                price_style = "color:#1D4ED8;font-weight:700;" if is_price else ""
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:4px 0;border-bottom:1px solid #F3F4F6;font-size:13px">'
                    f'<span style="color:#6B7280">{attr_name}</span>'
                    f'<span style="{price_style}">{level_val}</span></div>',
                    unsafe_allow_html=True
                )
            st.markdown("</div>", unsafe_allow_html=True)

            st.radio(
                "Select", ["Choose"],
                key=f"cbc_choice_t{task.task_number}_a{alt_idx}",
                label_visibility="collapsed",
            )

    # None column
    if include_none and len(cols) > n_alts:
        with cols[n_alts]:
            st.markdown(
                '<div style="border:1px dashed #D1D5DB;border-radius:10px;'
                'padding:12px 14px;min-height:160px;background:#F9FAFB;'
                'display:flex;align-items:center;justify-content:center;text-align:center">',
                unsafe_allow_html=True
            )
            st.markdown(
                '<div style="color:#6B7280;font-size:13px">I would not<br>choose any<br>of these.</div>',
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)
            st.radio(
                "Select", ["Choose"],
                key=f"cbc_choice_t{task.task_number}_none",
                label_visibility="collapsed",
            )

    st.write("")  # spacing between tasks


# ── MaxDiff set renderer ──────────────────────────────────────────────────────

def _render_maxdiff_set(md_set: MaxDiffSet, set_display_num: int) -> None:
    """Render one MaxDiff best/worst set."""
    st.markdown(
        f'<div style="font-size:14px;font-weight:600;margin:0 0 6px">Set {set_display_num}</div>',
        unsafe_allow_html=True
    )
    st.caption("Select the **BEST** (most important) and **WORST** (least important) item:")

    header_cols = st.columns([1, 5, 1])
    header_cols[0].markdown(
        '<div style="text-align:center;font-size:11px;font-weight:700;'
        'color:#16A34A">BEST</div>', unsafe_allow_html=True
    )
    header_cols[1].markdown("")
    header_cols[2].markdown(
        '<div style="text-align:center;font-size:11px;font-weight:700;'
        'color:#DC2626">WORST</div>', unsafe_allow_html=True
    )

    for pos_idx, item in enumerate(md_set.items):
        item_cols = st.columns([1, 5, 1])
        with item_cols[0]:
            st.checkbox(
                "", key=f"md_best_s{md_set.set_number}_b{md_set.block}_i{pos_idx}",
                label_visibility="collapsed"
            )
        with item_cols[1]:
            st.markdown(
                f'<div style="padding:6px 0;font-size:13px;border-bottom:1px solid #F3F4F6">'
                f'{item}</div>',
                unsafe_allow_html=True
            )
        with item_cols[2]:
            st.checkbox(
                "", key=f"md_worst_s{md_set.set_number}_b{md_set.block}_i{pos_idx}",
                label_visibility="collapsed"
            )

    st.write("")  # spacing


# ── Main render functions ─────────────────────────────────────────────────────

def _render_cbc_preview(design: CBCDesign) -> None:
    """Render the CBC survey preview with block selector."""
    col_block, col_info = st.columns([2, 3])

    with col_block:
        block_options = [f"Block {b}" for b in design.blocks]
        selected_label = st.selectbox("Survey block / version", block_options,
                                      key="preview_block_select")
        selected_block = int(selected_label.split()[1])
        st.session_state[SessionKeys.ACTIVE_BLOCK] = selected_block

    with col_info:
        tasks_in_block = design.get_block(selected_block)
        n_regular = sum(1 for t in tasks_in_block if not t.is_holdout)
        n_holdout = sum(1 for t in tasks_in_block if t.is_holdout)
        st.info(
            f"Block {selected_block}: **{n_regular} choice tasks** + "
            f"**{n_holdout} holdout task(s)**  |  "
            f"None option: {'Yes' if design.include_none else 'No'}"
        )

    st.divider()

    # Show tasks
    tasks = design.get_block(selected_block)
    display_num = 1
    for task in tasks:
        _render_cbc_task(task, design.include_none, display_num)
        if not task.is_holdout:
            display_num += 1
        st.divider()


def _render_maxdiff_preview(design: MaxDiffDesign) -> None:
    """Render the MaxDiff survey preview with block selector."""
    col_block, col_info = st.columns([2, 3])

    with col_block:
        block_options = [f"Block {b}" for b in design.blocks]
        selected_label = st.selectbox("Survey block / version", block_options,
                                      key="preview_md_block_select")
        selected_block = int(selected_label.split()[1])

    with col_info:
        sets_in_block = design.get_block(selected_block)
        st.info(
            f"Block {selected_block}: **{len(sets_in_block)} sets** · "
            f"{len(sets_in_block[0].items) if sets_in_block else 0} items per set"
        )

    st.divider()

    sets = design.get_block(selected_block)
    for i, md_set in enumerate(sets, start=1):
        _render_maxdiff_set(md_set, i)
        st.divider()


def render_preview_panel() -> None:
    """Render the survey preview panel (Step 3)."""
    study_type = st.session_state[SessionKeys.STUDY_TYPE]

    design = (
        st.session_state.get(SessionKeys.CBC_DESIGN)
        if study_type == "CBC"
        else st.session_state.get(SessionKeys.MAXDIFF_DESIGN)
    )

    if design is None:
        st.info("Generate a design first (Step 2) to see the survey preview.")
        return

    st.caption(
        "This is a pixel-faithful preview of what respondents will see. "
        "Radio buttons and checkboxes are for illustration only."
    )
    st.divider()

    if study_type == "CBC":
        _render_cbc_preview(design)
    else:
        _render_maxdiff_preview(design)
