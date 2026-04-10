"""
core/cbc_generator.py
---------------------
Coordinate Exchange algorithm for generating D-efficient CBC designs.

Algorithm summary:
  1. Initialize a random feasible design matrix.
  2. For each cell (task × alternative × attribute), try every other level.
     Keep the swap if it improves Bayesian D-efficiency.
  3. Repeat until no improvement is found (local optimum).
  4. Multi-start: repeat from step 1 N_STARTS times, return the global best.

References:
  Meyer & Nachtsheim (1995) — coordinate exchange for general designs
  Kessels et al. (2006)     — Bayesian D-optimal conjoint designs
"""

from __future__ import annotations

import random
import math
from copy import deepcopy
from typing import List, Tuple, Optional

import numpy as np

from core.models import CBCInput, CBCDesign, CBCTask, Attribute, Prohibition
from config.settings import CBC_DEFAULTS


# ── Effects coding helpers ─────────────────────────────────────────────────────

def effects_code(level_index: int, n_levels: int) -> List[float]:
    """
    Convert a level index to an effects-coded vector.

    For n_levels = 4:
      index 0 → [1, 0, 0]
      index 1 → [0, 1, 0]
      index 2 → [0, 0, 1]
      index 3 → [-1,-1,-1]   ← reference level
    """
    code = [0.0] * (n_levels - 1)
    if level_index < n_levels - 1:
        code[level_index] = 1.0
    else:
        code = [-1.0] * (n_levels - 1)
    return code


def profile_to_vector(profile: List[int], attributes: List[Attribute]) -> np.ndarray:
    """Convert a list of level indices into a full effects-coded parameter vector."""
    vec = []
    for attr_idx, level_idx in enumerate(profile):
        vec.extend(effects_code(level_idx, attributes[attr_idx].n_levels))
    return np.array(vec, dtype=float)


# ── Constraint checking ────────────────────────────────────────────────────────

def violates_prohibitions(
    profile: List[int],
    attributes: List[Attribute],
    prohibitions: List[Prohibition],
) -> bool:
    """Return True if the profile violates any defined prohibition."""
    attr_map = {a.name: i for i, a in enumerate(attributes)}
    for p in prohibitions:
        if p.attribute_a not in attr_map or p.attribute_b not in attr_map:
            continue
        idx_a = attr_map[p.attribute_a]
        idx_b = attr_map[p.attribute_b]
        if (attributes[idx_a].levels[profile[idx_a]] == p.level_a and
                attributes[idx_b].levels[profile[idx_b]] == p.level_b):
            return True
    return False


# ── D-efficiency computation ───────────────────────────────────────────────────

def compute_bayesian_d_efficiency(
    design: List[List[List[int]]],   # [task][alt][attr_idx] → level_idx
    attributes: List[Attribute],
    prior_variance: float = 1.0,
    n_monte_carlo: int = 200,
    rng: Optional[np.random.Generator] = None,
) -> float:
    """
    Compute Bayesian D-efficiency via Monte Carlo integration over the prior.

    For each Monte Carlo draw β ~ N(0, σ²I):
      1. Compute MNL choice probabilities for each task.
      2. Accumulate the Fisher information matrix Σ_t Σ_i p_it(1-p_it) x_it x_it'.
    Average across draws, then compute (det(I))^(1/p) / n_tasks * 100.

    Returns a percentage in [0, 100].
    """
    if rng is None:
        rng = np.random.default_rng(42)

    n_tasks = len(design)
    n_alts = len(design[0]) if n_tasks > 0 else 0
    n_params = sum(a.n_params for a in attributes)

    if n_params == 0 or n_tasks == 0 or n_alts == 0:
        return 0.0

    # Pre-compute X matrix: shape (n_tasks, n_alts, n_params)
    X = np.zeros((n_tasks, n_alts, n_params))
    for t, task in enumerate(design):
        for a, alt_profile in enumerate(task):
            X[t, a, :] = profile_to_vector(alt_profile, attributes)

    info_matrix = np.zeros((n_params, n_params))

    for _ in range(n_monte_carlo):
        beta = rng.normal(0, math.sqrt(prior_variance), n_params)

        for t in range(n_tasks):
            utilities = X[t] @ beta          # shape (n_alts,)
            # numerically stable softmax
            u_max = utilities.max()
            exp_u = np.exp(utilities - u_max)
            probs = exp_u / exp_u.sum()      # MNL probabilities

            # Xtilde = X_t - weighted mean (for variance computation)
            X_mean = (probs[:, None] * X[t]).sum(axis=0)  # shape (n_params,)
            for a in range(n_alts):
                diff = X[t, a] - X_mean
                info_matrix += probs[a] * np.outer(diff, diff)

    info_matrix /= n_monte_carlo

    # D-efficiency = det(I)^(1/p) / n_tasks * 100
    sign, log_det = np.linalg.slogdet(info_matrix)
    if sign <= 0:
        return 0.0

    d_eff = math.exp(log_det / n_params) / n_tasks * 100.0
    return min(d_eff, 100.0)


# ── Random initialization ─────────────────────────────────────────────────────

def random_design(
    n_tasks: int,
    n_alts: int,
    attributes: List[Attribute],
    prohibitions: List[Prohibition],
    rng: np.random.Generator,
    max_attempts: int = 10_000,
) -> List[List[List[int]]]:
    """
    Generate a random initial design matrix [task][alt][attr] → level_idx.
    Respects prohibitions by rejection sampling.
    """
    design = []
    for _ in range(n_tasks):
        task = []
        for _ in range(n_alts):
            for attempt in range(max_attempts):
                profile = [rng.integers(0, a.n_levels) for a in attributes]
                if not violates_prohibitions(profile, attributes, prohibitions):
                    task.append(profile)
                    break
            else:
                # Fall back: use first valid level combination
                profile = [0] * len(attributes)
                task.append(profile)
        design.append(task)
    return design


# ── Coordinate exchange optimizer ─────────────────────────────────────────────

def coordinate_exchange(
    inp: CBCInput,
    n_starts: int = 20,
    max_iter: int = 500,
    n_monte_carlo: int = 200,
    seed: int = 42,
    progress_callback=None,
) -> Tuple[List[List[List[int]]], float]:
    """
    Multi-start coordinate exchange to find a (locally) D-optimal design.

    Parameters
    ----------
    inp              : CBCInput with attributes and constraints
    n_starts         : number of random restarts
    max_iter         : max sweeps per start before declaring convergence
    n_monte_carlo    : MC draws for Bayesian D-efficiency
    seed             : RNG seed for reproducibility
    progress_callback: optional callable(pct: float, msg: str)

    Returns
    -------
    best_design      : List[List[List[int]]]
    best_efficiency  : float (percentage)
    """
    rng = np.random.default_rng(seed)
    best_design = None
    best_eff = -1.0
    attrs = inp.attributes
    n_tasks = inp.total_tasks

    for start in range(n_starts):
        if progress_callback:
            pct = (start / n_starts) * 90
            progress_callback(pct, f"Start {start + 1}/{n_starts} — best so far: {best_eff:.1f}%")

        design = random_design(n_tasks, inp.n_alternatives, attrs, inp.prohibitions, rng)
        current_eff = compute_bayesian_d_efficiency(
            design, attrs,
            prior_variance=inp.prior_variance,
            n_monte_carlo=n_monte_carlo,
            rng=rng,
        )

        for iteration in range(max_iter):
            improved = False
            task_order = list(range(n_tasks))
            rng.shuffle(task_order)  # random sweep order prevents bias

            for t in task_order:
                for a in range(inp.n_alternatives):
                    for attr_idx, attr in enumerate(attrs):
                        current_level = design[t][a][attr_idx]

                        for candidate_level in range(attr.n_levels):
                            if candidate_level == current_level:
                                continue

                            design[t][a][attr_idx] = candidate_level

                            # Check prohibitions
                            if violates_prohibitions(design[t][a], attrs, inp.prohibitions):
                                design[t][a][attr_idx] = current_level
                                continue

                            new_eff = compute_bayesian_d_efficiency(
                                design, attrs,
                                prior_variance=inp.prior_variance,
                                n_monte_carlo=n_monte_carlo,
                                rng=rng,
                            )

                            if new_eff > current_eff:
                                current_eff = new_eff
                                current_level = candidate_level
                                improved = True
                            else:
                                design[t][a][attr_idx] = current_level  # revert

            if not improved:
                break  # local optimum reached

        if current_eff > best_eff:
            best_eff = current_eff
            best_design = deepcopy(design)

    if progress_callback:
        progress_callback(95.0, "Applying blocking and holdout scheme...")

    return best_design, best_eff


# ── Complexity scoring for fatigue optimization ────────────────────────────────

def compute_task_complexity(task_profiles: List[List[int]], attributes: List[Attribute]) -> float:
    """
    Estimate cognitive complexity of a task.
    More unique level values shown → harder task.
    Price attributes count double (more cognitively demanding).
    """
    score = 0.0
    for attr_idx, attr in enumerate(attributes):
        levels_shown = {p[attr_idx] for p in task_profiles}
        weight = 2.0 if attr.is_price else 1.0
        score += len(levels_shown) * weight
    return score


# ── Blocking ──────────────────────────────────────────────────────────────────

def assign_blocks(
    design: List[List[List[int]]],
    attributes: List[Attribute],
    n_blocks: int,
    n_regular_tasks: int,
    n_holdout: int,
    fatigue_opt: bool = True,
) -> List[CBCTask]:
    """
    Assign tasks to blocks using a Latin-square-style round robin.
    Holdout tasks are appended to every block unchanged.
    If fatigue_opt=True, reorder tasks so difficult tasks appear mid-survey.
    """
    regular_tasks = design[:n_regular_tasks]
    holdout_raw = design[n_regular_tasks:]

    # Compute complexity scores
    complexities = [
        compute_task_complexity(task, attributes)
        for task in regular_tasks
    ]

    # Sort indices: easy → hard → easy (U-shaped) for fatigue optimization
    if fatigue_opt and len(complexities) > 2:
        sorted_idx = sorted(range(len(complexities)), key=lambda i: complexities[i])
        # Interleave: put medium tasks first, hard in middle, easy at end
        n = len(sorted_idx)
        reordered = []
        left, right = 0, n - 1
        toggle = True
        while left <= right:
            if toggle:
                reordered.append(sorted_idx[left]); left += 1
            else:
                reordered.append(sorted_idx[right]); right -= 1
            toggle = not toggle
        regular_tasks = [regular_tasks[i] for i in reordered]
        complexities = [complexities[i] for i in reordered]

    # Round-robin assignment to blocks
    tasks_per_block = math.ceil(n_regular_tasks / n_blocks)
    cbc_tasks = []
    task_num = 1

    for block in range(1, n_blocks + 1):
        start = (block - 1) * tasks_per_block
        end = min(start + tasks_per_block, n_regular_tasks)
        block_tasks = regular_tasks[start:end]

        for t_idx, raw_task in enumerate(block_tasks):
            alternatives = []
            for alt_profile in raw_task:
                profile_dict = {
                    attributes[ai].name: attributes[ai].levels[level_idx]
                    for ai, level_idx in enumerate(alt_profile)
                }
                alternatives.append(profile_dict)

            cbc_tasks.append(CBCTask(
                task_number=task_num,
                block=block,
                is_holdout=False,
                alternatives=alternatives,
                complexity_score=complexities[start + t_idx] if (start + t_idx) < len(complexities) else 0.0,
            ))
            task_num += 1

        # Append holdout tasks to this block
        for h_idx, h_raw in enumerate(holdout_raw):
            alternatives = []
            for alt_profile in h_raw:
                profile_dict = {
                    attributes[ai].name: attributes[ai].levels[level_idx]
                    for ai, level_idx in enumerate(alt_profile)
                }
                alternatives.append(profile_dict)

            cbc_tasks.append(CBCTask(
                task_number=task_num,
                block=block,
                is_holdout=True,
                alternatives=alternatives,
            ))
            task_num += 1

    return cbc_tasks


# ── Main public entry point ───────────────────────────────────────────────────

def generate_cbc_design(inp: CBCInput, progress_callback=None, seed: int = 42) -> CBCDesign:
    """
    Full pipeline: coordinate exchange → blocking → wrap in CBCDesign.

    Parameters
    ----------
    inp               : CBCInput
    progress_callback : optional callable(pct: float, msg: str)
    seed              : RNG seed

    Returns
    -------
    CBCDesign
    """
    n_starts = CBC_DEFAULTS["n_starts"]
    max_iter = CBC_DEFAULTS["max_iter"]
    n_mc = CBC_DEFAULTS["n_monte_carlo"] if inp.bayesian else 1

    best_design, d_eff = coordinate_exchange(
        inp,
        n_starts=n_starts,
        max_iter=max_iter,
        n_monte_carlo=n_mc,
        seed=seed,
        progress_callback=progress_callback,
    )

    if progress_callback:
        progress_callback(97.0, "Finalizing design structure...")

    n_regular = inp.n_tasks
    n_holdout = inp.n_holdout if inp.include_holdout else 0

    cbc_tasks = assign_blocks(
        best_design,
        inp.attributes,
        inp.n_blocks,
        n_regular,
        n_holdout,
        fatigue_opt=inp.fatigue_opt,
    )

    if progress_callback:
        progress_callback(100.0, "Done!")

    return CBCDesign(
        tasks=cbc_tasks,
        attributes=inp.attributes,
        n_blocks=inp.n_blocks,
        n_tasks_per_block=math.ceil(n_regular / inp.n_blocks),
        include_none=inp.include_none,
        metadata={
            "d_efficiency": d_eff,
            "n_starts": n_starts,
            "bayesian": inp.bayesian,
            "prior_variance": inp.prior_variance,
            "seed": seed,
        },
    )
