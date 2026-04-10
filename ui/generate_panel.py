"""
ui/generate_panel.py
--------------------
Step 2: Generate the design.
  - Validates inputs
  - Shows design summary statistics
  - Triggers the generation algorithm with a live progress bar
  - Shows the resulting design matrix in a table
"""

from __future__ import annotations

import time

import streamlit as st

from core import (
    generate_cbc_design, generate_maxdiff_design,
    validate_cbc, validate_maxdiff,
)
from exports import cbc_to_dataframe, maxdiff_to_dataframe
from utils.helpers import (
    SessionKeys, build_cbc_input, build_maxdiff_input,
    validate_cbc_inputs, validate_maxdiff_inputs,
)
from config.settings import CBC_DEFAULTS, MAXDIFF_DEFAULTS


# ── Design summary cards ──────────────────────────────────────────────────────

def _cbc_summary_metrics(inp) -> None:
    cols = st.columns(4)
    cols[0].metric("Attributes", len(inp.attributes))
    cols[1].metric("Parameters", inp.n_params)
    cols[2].metric("Full factorial", f"{inp.full_factorial_size:,}")
    cols[3].metric("Total tasks × alts", f"{inp.total_tasks * inp.n_alternatives:,}")

    cols2 = st.columns(4)
    cols2[0].metric("Tasks / respondent", inp.n_tasks)
    cols2[1].metric("Alternatives / task", inp.n_alternatives)
    cols2[2].metric("Blocks", inp.n_blocks)
    cols2[3].metric("Est. sample size", f"{inp.sample_size:,}")


def _maxdiff_summary_metrics(inp) -> None:
    cols = st.columns(4)
    cols[0].metric("Total items", inp.n_items)
    cols[1].metric("Items per set", inp.n_per_set)
    cols[2].metric("Sets required", inp.n_sets)
    cols[3].metric("BIBD λ", f"{inp.bibd_lambda:.2f}")

    cols2 = st.columns(4)
    cols2[0].metric("Target appearances", inp.target_appearances)
    cols2[1].metric("Blocks", inp.n_blocks)
    cols2[2].metric("Total comparisons", inp.n_sets * inp.n_per_set)
    cols2[3].metric("", "")


# ── Generation progress callback ─────────────────────────────────────────────

def _make_progress_callback(progress_bar, status_text):
    """Return a callback that updates the Streamlit progress bar."""
    def callback(pct: float, msg: str) -> None:
        progress_bar.progress(min(int(pct), 100), text=msg)
        status_text.caption(msg)
    return callback


# ── CBC generation ────────────────────────────────────────────────────────────

def _run_cbc_generation(inp) -> None:
    """Run the CBC generator and store results in session state."""
    progress_bar = st.progress(0, text="Starting...")
    status_text = st.empty()

    callback = _make_progress_callback(progress_bar, status_text)

    seed = st.session_state.get(SessionKeys.SEED, 42)

    start_time = time.time()
    design = generate_cbc_design(inp, progress_callback=callback, seed=seed)
    elapsed = time.time() - start_time

    diagnostics = validate_cbc(design, inp)

    st.session_state[SessionKeys.CBC_DESIGN] = design
    st.session_state[SessionKeys.CBC_DIAGNOSTICS] = diagnostics
    st.session_state[SessionKeys.ACTIVE_BLOCK] = 1

    progress_bar.empty()
    status_text.empty()

    st.success(
        f"✓ Design generated in {elapsed:.1f}s · "
        f"D-efficiency: **{diagnostics.d_efficiency:.1f}%** · "
        f"Grade: **{diagnostics.overall_grade}**"
    )


# ── MaxDiff generation ────────────────────────────────────────────────────────

def _run_maxdiff_generation(inp) -> None:
    """Run the MaxDiff generator and store results in session state."""
    progress_bar = st.progress(0, text="Starting...")
    status_text = st.empty()

    callback = _make_progress_callback(progress_bar, status_text)

    seed = st.session_state.get(SessionKeys.SEED, 42)

    start_time = time.time()
    design = generate_maxdiff_design(inp, progress_callback=callback, seed=seed)
    elapsed = time.time() - start_time

    diagnostics = validate_maxdiff(design, inp)

    st.session_state[SessionKeys.MAXDIFF_DESIGN] = design
    st.session_state[SessionKeys.MAXDIFF_DIAGNOSTICS] = diagnostics
    st.session_state[SessionKeys.ACTIVE_BLOCK] = 1

    progress_bar.empty()
    status_text.empty()

    app_counts = list(design.appearance_counts.values())
    st.success(
        f"✓ Design generated in {elapsed:.1f}s · "
        f"Appearances: {min(app_counts)}–{max(app_counts)} · "
        f"Pair coverage: **{design.metadata.get('pair_coverage_pct', 0):.1f}%**"
    )


# ── Design matrix preview ─────────────────────────────────────────────────────

def _show_cbc_matrix(design) -> None:
    """Show the CBC design matrix as a paginated dataframe."""
    st.subheader("Design matrix")

    block_options = [f"Block {b}" for b in design.blocks]
    selected_block_label = st.selectbox("View block", block_options, key="gen_block_select")
    selected_block = int(selected_block_label.split()[1])

    df = cbc_to_dataframe(design)
    block_df = df[df["Block"] == selected_block].reset_index(drop=True)

    # Style holdout rows
    def highlight_holdout(row):
        if row["Holdout"] == 1:
            return ["background-color: #FEF3C7"] * len(row)
        return [""] * len(row)

    styled = block_df.style.apply(highlight_holdout, axis=1)
    st.dataframe(styled, use_container_width=True, height=400)
    st.caption(
        f"Block {selected_block}: {len(block_df[block_df['Holdout']==0]) // design.n_tasks_per_block} tasks "
        f"(yellow = holdout) · "
        f"Total design: {len(df)} rows across {design.n_blocks} blocks"
    )


def _show_maxdiff_matrix(design) -> None:
    """Show the MaxDiff design matrix as a dataframe."""
    st.subheader("Design matrix")

    block_options = [f"Block {b}" for b in design.blocks]
    selected_block_label = st.selectbox("View block", block_options, key="gen_md_block")
    selected_block = int(selected_block_label.split()[1])

    df = maxdiff_to_dataframe(design)
    block_df = df[df["Block"] == selected_block].reset_index(drop=True)

    st.dataframe(block_df, use_container_width=True, height=400)
    st.caption(
        f"Block {selected_block}: {len(block_df['Set'].unique())} sets · "
        f"Total items shown: {len(block_df)}"
    )


# ── Main render function ──────────────────────────────────────────────────────

def render_generate_panel() -> None:
    """Render the generation panel (Step 2)."""
    study_type = st.session_state[SessionKeys.STUDY_TYPE]

    # ── Build inputs from session state ──
    if study_type == "CBC":
        attrs = st.session_state[SessionKeys.ATTRIBUTES]
        prohibitions = st.session_state[SessionKeys.PROHIBITIONS]
        inp = build_cbc_input(
            attributes=attrs,
            prohibitions=prohibitions,
            n_tasks=st.session_state.get("cbc_n_tasks", CBC_DEFAULTS["n_tasks"]),
            n_alts=st.session_state.get("cbc_n_alts", CBC_DEFAULTS["n_alternatives"]),
            n_blocks=st.session_state.get("cbc_n_blocks", CBC_DEFAULTS["n_blocks"]),
            n_holdout=st.session_state.get("cbc_n_holdout", CBC_DEFAULTS["n_holdout"]),
            sample_size=st.session_state.get("cbc_sample_size", CBC_DEFAULTS["sample_size"]),
            include_none=st.session_state.get("cbc_include_none", CBC_DEFAULTS["include_none"]),
            include_holdout=st.session_state.get("cbc_include_holdout", CBC_DEFAULTS["include_holdout"]),
            dual_none=st.session_state.get("cbc_dual_none", CBC_DEFAULTS["dual_none"]),
            bayesian=st.session_state.get("cbc_bayesian", CBC_DEFAULTS["bayesian"]),
            prior_variance=st.session_state.get("cbc_prior_variance", CBC_DEFAULTS["prior_variance"]),
            fatigue_opt=st.session_state.get("cbc_fatigue_opt", CBC_DEFAULTS["fatigue_opt"]),
        )
        errors = validate_cbc_inputs(inp)
    else:
        inp = build_maxdiff_input(
            items=st.session_state[SessionKeys.ITEMS],
            n_per_set=st.session_state.get("md_per_set", MAXDIFF_DEFAULTS["n_per_set"]),
            target_appearances=st.session_state.get("md_target_app", MAXDIFF_DEFAULTS["target_appearances"]),
            n_blocks=st.session_state.get("md_n_blocks", MAXDIFF_DEFAULTS["n_blocks"]),
            position_balance=st.session_state.get("md_pos_balance", MAXDIFF_DEFAULTS["position_balance"]),
            pair_optimization=st.session_state.get("md_pair_opt", MAXDIFF_DEFAULTS["pair_optimization"]),
            anchored=st.session_state.get("md_anchored", MAXDIFF_DEFAULTS["anchored"]),
        )
        errors = validate_maxdiff_inputs(inp)

    # ── Design summary ──
    st.subheader("Design summary")
    if study_type == "CBC":
        _cbc_summary_metrics(inp)
    else:
        _maxdiff_summary_metrics(inp)

    st.divider()

    # ── Validation errors ──
    if errors:
        for err in errors:
            st.error(f"✕ {err}")
        st.stop()

    # ── RNG seed control ──
    col_seed, col_gen = st.columns([2, 3])
    with col_seed:
        st.session_state[SessionKeys.SEED] = st.number_input(
            "Random seed (for reproducibility)",
            min_value=0, max_value=9999,
            value=st.session_state.get(SessionKeys.SEED, 42),
            key="seed_input",
        )

    with col_gen:
        st.write("")  # vertical align
        generate_clicked = st.button(
            "🔬 Generate design",
            type="primary",
            use_container_width=True,
            help="Runs the coordinate exchange optimizer. Takes 5–30 seconds depending on design size."
        )

    if generate_clicked:
        st.session_state[SessionKeys.CBC_INPUT] = inp if study_type == "CBC" else None
        st.session_state[SessionKeys.MAXDIFF_INPUT] = inp if study_type == "MaxDiff" else None

        with st.spinner(""):
            if study_type == "CBC":
                _run_cbc_generation(inp)
            else:
                _run_maxdiff_generation(inp)

    st.divider()

    # ── Show matrix if design exists ──
    design = (
        st.session_state.get(SessionKeys.CBC_DESIGN)
        if study_type == "CBC"
        else st.session_state.get(SessionKeys.MAXDIFF_DESIGN)
    )

    if design is not None:
        if study_type == "CBC":
            _show_cbc_matrix(design)
        else:
            _show_maxdiff_matrix(design)
    else:
        st.info("Click **Generate design** to create a design. Generation takes 5–30 seconds.")
