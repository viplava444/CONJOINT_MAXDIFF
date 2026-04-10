"""
core/validator.py
-----------------
Statistical validation and diagnostics for generated designs.

Computes:
  - D-efficiency (Bayesian, CBC) / Balance score (MaxDiff)
  - Per-attribute level balance (chi-squared test)
  - Attribute independence (Spearman correlation matrix)
  - Task overlap percentage (CBC)
  - Standard error estimates
  - Item appearance variance (MaxDiff)
  - Pair coverage percentage (MaxDiff)
  - Actionable warnings and recommendations
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from core.models import (
    CBCDesign,
    CBCInput,
    DiagnosticsReport,
    LevelBalance,
    MaxDiffDesign,
    MaxDiffInput,
)
from core.cbc_generator import compute_bayesian_d_efficiency
from config.settings import (
    D_EFFICIENCY_GOOD,
    D_EFFICIENCY_WARN,
    MAX_ATTR_CORRELATION,
    OVERLAP_WARN_PCT,
    BALANCE_CHI2_ALPHA,
)


# ── CBC Diagnostics ───────────────────────────────────────────────────────────

def _build_cbc_level_df(design: CBCDesign) -> pd.DataFrame:
    """
    Flatten the CBC design into a DataFrame with one row per
    (task, alternative, attribute, level) observation.
    """
    rows = []
    for task in design.tasks:
        if task.is_holdout:
            continue
        for alt in task.alternatives:
            for attr_name, level_val in alt.items():
                rows.append({
                    "task": task.task_number,
                    "block": task.block,
                    "attr": attr_name,
                    "level": level_val,
                })
    return pd.DataFrame(rows)


def _level_balance(df: pd.DataFrame, design: CBCDesign) -> List[LevelBalance]:
    """Compute chi-squared balance test for each attribute."""
    results = []
    for attr in design.attributes:
        attr_df = df[df["attr"] == attr.name]
        counts = attr_df["level"].value_counts().to_dict()
        # Fill zeros for any missing levels
        for lvl in attr.levels:
            counts.setdefault(lvl, 0)

        total = sum(counts.values())
        expected = total / attr.n_levels if attr.n_levels > 0 else 1.0

        chi2 = sum((counts.get(lvl, 0) - expected) ** 2 / expected for lvl in attr.levels)
        df_chi2 = attr.n_levels - 1
        critical = stats.chi2.ppf(1 - BALANCE_CHI2_ALPHA, df=df_chi2) if df_chi2 > 0 else 0.0
        is_balanced = chi2 <= critical

        results.append(LevelBalance(
            attribute_name=attr.name,
            counts=counts,
            expected_count=expected,
            chi2_stat=chi2,
            is_balanced=is_balanced,
        ))
    return results


def _attr_correlation_matrix(df: pd.DataFrame, design: CBCDesign) -> pd.DataFrame:
    """
    Build a Spearman correlation matrix between attribute level columns.
    Levels are label-encoded as integers.
    """
    encoded = {}
    for attr in design.attributes:
        level_map = {lvl: i for i, lvl in enumerate(attr.levels)}
        col = df[df["attr"] == attr.name].groupby("task")["level"].apply(
            lambda x: level_map.get(x.iloc[0], 0)
        )
        encoded[attr.name] = col

    pivot = pd.DataFrame(encoded).dropna()
    if pivot.empty or pivot.shape[1] < 2:
        return pd.DataFrame()

    corr, _ = stats.spearmanr(pivot)
    if isinstance(corr, float):
        # Only 2 attributes → scalar result
        corr = np.array([[1.0, corr], [corr, 1.0]])

    return pd.DataFrame(corr, index=pivot.columns, columns=pivot.columns)


def _overlap_percentage(design: CBCDesign) -> float:
    """
    Percentage of (non-holdout) tasks where at least one attribute
    has the same level in two or more alternatives.
    """
    overlap_count = 0
    total = 0
    for task in design.tasks:
        if task.is_holdout:
            continue
        total += 1
        for attr in design.attributes:
            levels_in_task = [alt.get(attr.name) for alt in task.alternatives]
            if len(levels_in_task) != len(set(levels_in_task)):
                overlap_count += 1
                break  # count each task at most once

    return 100.0 * overlap_count / total if total > 0 else 0.0


def validate_cbc(design: CBCDesign, inp: CBCInput) -> DiagnosticsReport:
    """
    Compute the full diagnostics report for a CBC design.
    """
    # Build flat dataframe
    df = _build_cbc_level_df(design)

    # D-efficiency from stored metadata (already computed during generation)
    d_eff = design.metadata.get("d_efficiency", 0.0)

    # Level balance
    level_balance = _level_balance(df, design)

    # Attribute correlation
    corr_matrix = _attr_correlation_matrix(df, design)
    max_corr = 0.0
    if not corr_matrix.empty:
        mask = np.ones(corr_matrix.shape, dtype=bool)
        np.fill_diagonal(mask, False)
        max_corr = float(corr_matrix.values[mask].max()) if mask.any() else 0.0

    # Overlap
    overlap_pct = _overlap_percentage(design)

    # Expected SE per parameter (approximate)
    n_tasks = sum(1 for t in design.tasks if not t.is_holdout)
    n_obs = n_tasks * inp.n_alternatives * inp.sample_size
    n_params = inp.n_params
    expected_se = (
        1.0 / math.sqrt(n_obs * d_eff / 100.0 * n_params)
        if (n_obs > 0 and d_eff > 0 and n_params > 0)
        else float("nan")
    )

    # Warnings and recommendations
    warnings: List[str] = []
    recommendations: List[str] = []

    if d_eff < D_EFFICIENCY_WARN:
        warnings.append(f"D-efficiency ({d_eff:.1f}%) is below the acceptable threshold of {D_EFFICIENCY_WARN}%.")
        recommendations.append("Add 2–3 more tasks per respondent, or reduce the number of attributes.")
    elif d_eff < D_EFFICIENCY_GOOD:
        warnings.append(f"D-efficiency ({d_eff:.1f}%) is marginal. Consider adding 1–2 tasks.")

    if max_corr >= MAX_ATTR_CORRELATION:
        warnings.append(f"Max attribute correlation ({max_corr:.3f}) exceeds threshold ({MAX_ATTR_CORRELATION}). Attributes are not fully independent.")
        recommendations.append("Increase n_tasks or remove/merge correlated attributes.")

    if overlap_pct > OVERLAP_WARN_PCT:
        warnings.append(f"Task overlap ({overlap_pct:.1f}%) is high. Respondents see repeated levels frequently.")
        recommendations.append("Enable 'minimal overlap' constraint or increase alternatives per task.")

    unbalanced = [b.attribute_name for b in level_balance if not b.is_balanced]
    if unbalanced:
        warnings.append(f"Level imbalance detected in: {', '.join(unbalanced)}.")
        recommendations.append("Regenerate design; the coordinate exchange may have converged to a local optimum.")

    return DiagnosticsReport(
        study_type="CBC",
        d_efficiency=d_eff,
        level_balance=level_balance,
        max_attr_correlation=max_corr,
        correlation_matrix=corr_matrix,
        overlap_pct=overlap_pct,
        expected_se=expected_se,
        appearance_variance=0.0,
        pair_coverage_pct=100.0,
        warnings=warnings,
        recommendations=recommendations,
    )


# ── MaxDiff Diagnostics ───────────────────────────────────────────────────────

def validate_maxdiff(design: MaxDiffDesign, inp: MaxDiffInput) -> DiagnosticsReport:
    """
    Compute the full diagnostics report for a MaxDiff design.
    """
    appearance_counts = design.appearance_counts
    n_items = len(inp.items)

    # Appearance variance
    counts = list(appearance_counts.values())
    mean_app = sum(counts) / len(counts) if counts else 0
    app_var = sum((c - mean_app) ** 2 for c in counts) / len(counts) if counts else 0.0

    # Build "level balance" objects for each item's appearance count
    level_balance = [
        LevelBalance(
            attribute_name=item,
            counts={item: appearance_counts.get(item, 0)},
            expected_count=float(inp.target_appearances),
            chi2_stat=abs(appearance_counts.get(item, 0) - inp.target_appearances),
            is_balanced=abs(appearance_counts.get(item, 0) - inp.target_appearances) <= 1,
        )
        for item in inp.items
    ]

    # Pair coverage
    pair_coverage_pct = design.metadata.get("pair_coverage_pct", 0.0)

    # D-efficiency proxy: use appearance balance (0 = perfect BIBD)
    # Map app_var to a 0–100 scale where 0 variance → 100% "efficiency"
    max_possible_var = (inp.target_appearances) ** 2
    d_eff_proxy = max(0.0, 100.0 - (app_var / max(max_possible_var, 1e-9)) * 100.0)

    # Expected SE for MaxDiff (Sawtooth approximation)
    n_sets = len([s for s in design.sets if s.block == 1])  # per block
    expected_se = 1.0 / math.sqrt(n_sets * inp.n_per_set) if n_sets > 0 else float("nan")

    # Correlation matrix — not directly applicable for MaxDiff items
    corr_matrix = pd.DataFrame()

    # Warnings
    warnings: List[str] = []
    recommendations: List[str] = []

    imbalanced_items = [item for item in inp.items
                        if abs(appearance_counts.get(item, 0) - inp.target_appearances) > 1]
    if imbalanced_items:
        warnings.append(f"{len(imbalanced_items)} items appear ≥2 times away from target ({inp.target_appearances}).")
        recommendations.append("Increase n_sets (add 1–2 more tasks) to improve balance.")

    if pair_coverage_pct < 80.0:
        warnings.append(f"Only {pair_coverage_pct:.1f}% of item pairs ever appear in the same set.")
        recommendations.append("Increase target_appearances or reduce items per set to improve pair coverage.")

    if inp.n_items < 5:
        warnings.append("Fewer than 5 items: MaxDiff provides limited discrimination. Consider adding items.")

    if inp.n_items > 30 and inp.n_per_set < 5:
        recommendations.append("With 30+ items, consider 5 items per set to reduce the total number of sets.")

    return DiagnosticsReport(
        study_type="MaxDiff",
        d_efficiency=d_eff_proxy,
        level_balance=level_balance,
        max_attr_correlation=0.0,
        correlation_matrix=corr_matrix,
        overlap_pct=0.0,
        expected_se=expected_se,
        appearance_variance=app_var,
        pair_coverage_pct=pair_coverage_pct,
        warnings=warnings,
        recommendations=recommendations,
    )
