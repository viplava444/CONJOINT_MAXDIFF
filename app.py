"""
app.py
------
Conjoint & MaxDiff Design Engine — main Streamlit entry point.

Run with:
    streamlit run app.py

Architecture:
    app.py              ← this file: page layout, navigation, sidebar
    config/settings.py  ← all constants and defaults
    core/               ← pure-Python generation & validation logic
    ui/                 ← Streamlit panel components
    exports/            ← file-generation functions
    utils/              ← charts, session helpers, formatting
"""

import streamlit as st

from config.settings import APP_TITLE, APP_ICON, APP_LAYOUT, PRESET_ATTRIBUTES, PRESET_MAXDIFF_ITEMS
from utils.helpers import SessionKeys, init_session_state
from ui import (
    render_config_panel,
    render_generate_panel,
    render_preview_panel,
    render_diagnostics_panel,
    render_export_panel,
)

# ── Page configuration (must be first Streamlit call) ─────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Tighten main content padding */
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    /* Step tab styling */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        padding: 0 20px;
        border-radius: 8px 8px 0 0;
        font-size: 14px;
        font-weight: 500;
    }

    /* Metric card tweaks */
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    [data-testid="stMetricDelta"] { font-size: 0.78rem; }

    /* Sidebar section headers */
    .sidebar-header {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #9CA3AF;
        margin: 1rem 0 0.5rem;
    }

    /* Remove dataframe index column */
    [data-testid="stDataFrame"] thead tr th:first-child { display: none; }
    [data-testid="stDataFrame"] tbody tr td:first-child { display: none; }

    /* Design card rendering in preview */
    .alt-card {
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 12px 14px;
    }
</style>
""", unsafe_allow_html=True)

# ── Initialise session state ──────────────────────────────────────────────────
default_attrs = [dict(a) for a in PRESET_ATTRIBUTES["TV / Consumer Electronics"]]
default_items = list(PRESET_MAXDIFF_ITEMS["Brand Attributes"])
init_session_state(default_attrs, default_items)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Statistically efficient survey design for market research.")
    st.divider()

    # Study type switcher
    st.markdown('<div class="sidebar-header">Study Type</div>', unsafe_allow_html=True)
    study_type = st.radio(
        "Study type",
        options=["CBC", "MaxDiff"],
        index=0 if st.session_state[SessionKeys.STUDY_TYPE] == "CBC" else 1,
        label_visibility="collapsed",
        horizontal=True,
        help=(
            "CBC (Choice-Based Conjoint): respondents choose between product profiles.\n"
            "MaxDiff: respondents pick the best and worst item from each set."
        ),
    )

    if study_type != st.session_state[SessionKeys.STUDY_TYPE]:
        st.session_state[SessionKeys.STUDY_TYPE] = study_type
        # Reset designs when switching study type
        st.session_state[SessionKeys.CBC_DESIGN] = None
        st.session_state[SessionKeys.MAXDIFF_DESIGN] = None
        st.session_state[SessionKeys.CBC_DIAGNOSTICS] = None
        st.session_state[SessionKeys.MAXDIFF_DIAGNOSTICS] = None
        st.rerun()

    st.divider()

    # Status summary
    st.markdown('<div class="sidebar-header">Status</div>', unsafe_allow_html=True)

    if study_type == "CBC":
        attrs = st.session_state[SessionKeys.ATTRIBUTES]
        valid_attrs = [a for a in attrs if len(a.get("levels", [])) >= 2]
        design = st.session_state.get(SessionKeys.CBC_DESIGN)
        diag = st.session_state.get(SessionKeys.CBC_DIAGNOSTICS)

        st.markdown(f"**Attributes configured:** {len(valid_attrs)}")
        if design:
            d_eff = design.metadata.get("d_efficiency", 0.0)
            color = "#22C55E" if d_eff >= 80 else "#F59E0B" if d_eff >= 65 else "#EF4444"
            st.markdown(
                f'Design: <span style="color:{color};font-weight:700">'
                f'D-eff {d_eff:.1f}%</span>',
                unsafe_allow_html=True,
            )
            st.markdown(f"Blocks: {design.n_blocks} · Tasks: {design.n_tasks_per_block}/block")
        else:
            st.markdown("Design: *not generated yet*")
    else:
        items = st.session_state[SessionKeys.ITEMS]
        valid_items = [i for i in items if i.strip()]
        design = st.session_state.get(SessionKeys.MAXDIFF_DESIGN)

        st.markdown(f"**Items configured:** {len(valid_items)}")
        if design:
            app_vals = list(design.appearance_counts.values())
            st.markdown(
                f"Design: {len(design.sets)} sets · "
                f"Appearances: {min(app_vals)}–{max(app_vals)}"
            )
        else:
            st.markdown("Design: *not generated yet*")

    st.divider()

    # Help / about
    with st.expander("About this tool"):
        st.markdown("""
**Conjoint & MaxDiff Design Engine** generates statistically efficient survey designs using:

- **Coordinate Exchange** algorithm (Meyer & Nachtsheim, 1995)
- **Bayesian D-efficiency** criterion (Kessels et al., 2006)
- **Near-BIBD** generation with swap optimization

**Methodology references:**
- Louviere et al. (2000) — Stated Choice Methods
- Sawtooth Software (2021) — CBC Technical Paper
- Cohen (2003) — MaxDiff Analysis

*v1.0.0 · Open source*
        """)

    st.markdown(
        '<div style="font-size:11px;color:#9CA3AF;margin-top:1rem">'
        'Built with Streamlit · Python 3.10+</div>',
        unsafe_allow_html=True
    )

# ── Main content area ─────────────────────────────────────────────────────────
st.title(f"{'CBC Conjoint' if study_type == 'CBC' else 'MaxDiff / Best-Worst'} Design Engine")
st.caption(
    "Step through the tabs to configure, generate, preview, validate, and export your survey design."
)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1 · Configure",
    "2 · Generate",
    "3 · Preview",
    "4 · Diagnostics",
    "5 · Export",
])

with tab1:
    render_config_panel()

with tab2:
    render_generate_panel()

with tab3:
    render_preview_panel()

with tab4:
    render_diagnostics_panel()

with tab5:
    render_export_panel()
