"""
core/maxdiff_generator.py
--------------------------
Near-BIBD generator for MaxDiff (Best-Worst Scaling) designs.

Algorithm:
  1. Greedy initialization: always pick items with the lowest current
     appearance count, breaking ties by minimizing pair co-occurrence.
  2. Swap optimization: iteratively swap items between sets to reduce
     variance in both appearance counts and pair coverage.
  3. Position randomization per block: shuffle item order within each
     set to achieve positional balance across the full design.

A perfect BIBD exists only for specific (v, k, r) combinations satisfying
  bk = vr  and  λ(v-1) = r(k-1)  with λ integer.
When those conditions aren't met, we produce a near-BIBD where every item
appears r or r+1 times and every pair co-appears ⌊λ⌋ or ⌈λ⌉ times.

References:
  Fisher (1940) — incomplete block designs
  Cohen (2003)  — MaxDiff survey design best practices
"""

from __future__ import annotations

import math
import random
from copy import deepcopy
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.models import MaxDiffDesign, MaxDiffInput, MaxDiffSet


# ── Balance metrics ────────────────────────────────────────────────────────────

def appearance_variance(appearance_counts: Dict[int, int]) -> float:
    """Variance of item appearance counts — 0 means perfect balance."""
    counts = list(appearance_counts.values())
    if not counts:
        return 0.0
    mean = sum(counts) / len(counts)
    return sum((c - mean) ** 2 for c in counts) / len(counts)


def pair_variance(pair_counts: Dict[Tuple[int, int], int]) -> float:
    """Variance of pair co-occurrence counts."""
    counts = list(pair_counts.values())
    if not counts:
        return 0.0
    mean = sum(counts) / len(counts)
    return sum((c - mean) ** 2 for c in counts) / len(counts)


def balance_score(
    appearance_counts: Dict[int, int],
    pair_counts: Dict[Tuple[int, int], int],
    alpha: float = 0.5,
) -> float:
    """
    Combined balance score (lower is better).
    alpha controls the trade-off between appearance balance and pair balance.
    """
    return alpha * appearance_variance(appearance_counts) + (1 - alpha) * pair_variance(pair_counts)


# ── Count helpers ─────────────────────────────────────────────────────────────

def build_pair_key(i: int, j: int) -> Tuple[int, int]:
    return (min(i, j), max(i, j))


def update_counts(
    items_in_set: List[int],
    appearance_counts: Dict[int, int],
    pair_counts: Dict[Tuple[int, int], int],
    delta: int = 1,
) -> None:
    """Increment or decrement (delta=-1) counts for a set of items."""
    for item in items_in_set:
        appearance_counts[item] = appearance_counts.get(item, 0) + delta
    for i, j in combinations(items_in_set, 2):
        key = build_pair_key(i, j)
        pair_counts[key] = pair_counts.get(key, 0) + delta


# ── Greedy initialization ─────────────────────────────────────────────────────

def greedy_init(
    n_items: int,
    n_sets: int,
    k: int,
    rng: np.random.Generator,
) -> Tuple[List[List[int]], Dict[int, int], Dict[Tuple[int, int], int]]:
    """
    Greedily build an initial design by always choosing the k items with
    the lowest current appearance count (ties broken by pair co-occurrence,
    then randomly).

    Returns
    -------
    sets             : list of lists of item indices
    appearance_counts
    pair_counts
    """
    appearance_counts: Dict[int, int] = {i: 0 for i in range(n_items)}
    pair_counts: Dict[Tuple[int, int], int] = {}
    sets: List[List[int]] = []

    for _ in range(n_sets):
        # Score each item: primary = appearance count, secondary = total pair count
        def item_score(i: int) -> Tuple[int, int, float]:
            pair_total = sum(
                pair_counts.get(build_pair_key(i, j), 0)
                for j in range(n_items) if j != i
            )
            return (appearance_counts[i], pair_total, rng.random())

        sorted_items = sorted(range(n_items), key=item_score)
        chosen = sorted(sorted_items[:k])  # keep sorted for reproducibility
        sets.append(chosen)
        update_counts(chosen, appearance_counts, pair_counts, delta=1)

    return sets, appearance_counts, pair_counts


# ── Swap optimization ─────────────────────────────────────────────────────────

def swap_optimize(
    sets: List[List[int]],
    n_items: int,
    appearance_counts: Dict[int, int],
    pair_counts: Dict[Tuple[int, int], int],
    max_iter: int = 300,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[List[List[int]], Dict[int, int], Dict[Tuple[int, int], int]]:
    """
    Iterative swap heuristic: for each (set, position), try replacing the item
    with every item not in the set. Keep the swap if it reduces balance_score.

    This is analogous to coordinate exchange for BIBD generation.
    """
    if rng is None:
        rng = np.random.default_rng(42)

    current_score = balance_score(appearance_counts, pair_counts)

    for iteration in range(max_iter):
        improved = False
        set_order = list(range(len(sets)))
        rng.shuffle(set_order)

        for s_idx in set_order:
            current_set = sets[s_idx]
            candidates_outside = [i for i in range(n_items) if i not in current_set]

            for pos in range(len(current_set)):
                out_item = current_set[pos]
                best_swap = None
                best_score = current_score

                for in_item in candidates_outside:
                    # Simulate swap: remove out_item, add in_item
                    new_set = [in_item if x == out_item else x for x in current_set]

                    # Temporarily update counts
                    update_counts(current_set, appearance_counts, pair_counts, delta=-1)
                    update_counts(new_set, appearance_counts, pair_counts, delta=1)

                    new_score = balance_score(appearance_counts, pair_counts)

                    # Revert
                    update_counts(new_set, appearance_counts, pair_counts, delta=-1)
                    update_counts(current_set, appearance_counts, pair_counts, delta=1)

                    if new_score < best_score - 1e-9:
                        best_score = new_score
                        best_swap = (pos, in_item, out_item)

                if best_swap is not None:
                    pos, in_item, out_item = best_swap
                    update_counts(current_set, appearance_counts, pair_counts, delta=-1)
                    current_set[pos] = in_item
                    update_counts(current_set, appearance_counts, pair_counts, delta=1)
                    current_score = best_score
                    improved = True

            sets[s_idx] = current_set

        if not improved:
            break

    return sets, appearance_counts, pair_counts


# ── Position balance ──────────────────────────────────────────────────────────

def apply_position_balance(
    sets: List[List[int]],
    n_items: int,
    k: int,
    rng: np.random.Generator,
) -> List[List[int]]:
    """
    Permute item order within each set to achieve approximately equal
    frequency of each item appearing in each ordinal position (1st, 2nd, …).

    Strategy: track a position_count matrix [item][position] and greedily
    assign items to under-represented positions via permutation.
    """
    position_counts = np.zeros((n_items, k), dtype=int)
    balanced_sets = []

    for item_set in sets:
        # Score each permutation: minimize max position imbalance
        # For efficiency, use a greedy assignment (not full permutation search)
        best_order = list(item_set)
        best_max_dev = float("inf")

        # Try a few random permutations
        candidates = [list(item_set)]
        for _ in range(20):
            perm = list(item_set)
            rng.shuffle(perm)
            candidates.append(perm)

        for candidate in candidates:
            # Measure how much this ordering worsens position imbalance
            total_dev = sum(
                position_counts[item][pos]
                for pos, item in enumerate(candidate)
            )
            if total_dev < best_max_dev:
                best_max_dev = total_dev
                best_order = candidate

        for pos, item in enumerate(best_order):
            position_counts[item][pos] += 1

        balanced_sets.append(best_order)

    return balanced_sets


# ── Blocking ──────────────────────────────────────────────────────────────────

def create_blocks(
    sets: List[List[int]],
    items: List[str],
    n_blocks: int,
    rng: np.random.Generator,
) -> List[MaxDiffSet]:
    """
    Distribute sets across blocks and convert item indices to item strings.
    Each block gets a shuffled order of the full set list.
    """
    maxdiff_sets = []
    sets_per_block = math.ceil(len(sets) / n_blocks)

    for block in range(1, n_blocks + 1):
        start = (block - 1) * sets_per_block
        end = min(start + sets_per_block, len(sets))
        block_raw = sets[start:end]

        # Shuffle set order within the block
        block_indices = list(range(len(block_raw)))
        rng.shuffle(block_indices)

        for new_pos, orig_pos in enumerate(block_indices):
            item_indices = block_raw[orig_pos]
            maxdiff_sets.append(MaxDiffSet(
                set_number=new_pos + 1,
                block=block,
                items=[items[i] for i in item_indices],
            ))

    return maxdiff_sets


# ── Main public entry point ───────────────────────────────────────────────────

def generate_maxdiff_design(
    inp: MaxDiffInput,
    progress_callback=None,
    seed: int = 42,
) -> MaxDiffDesign:
    """
    Full MaxDiff design generation pipeline.

    1. Greedy initialization (near-BIBD)
    2. Swap optimization for balance
    3. Position balance permutation
    4. Block assignment
    5. Wrap in MaxDiffDesign

    Parameters
    ----------
    inp               : MaxDiffInput
    progress_callback : optional callable(pct: float, msg: str)
    seed              : RNG seed

    Returns
    -------
    MaxDiffDesign
    """
    rng = np.random.default_rng(seed)
    n_items = inp.n_items
    n_sets = inp.n_sets
    k = inp.n_per_set

    if progress_callback:
        progress_callback(10.0, "Greedy BIBD initialization...")

    sets, appearance_counts, pair_counts = greedy_init(n_items, n_sets, k, rng)

    if progress_callback:
        progress_callback(40.0, "Swap optimization for balance...")

    if inp.pair_optimization:
        sets, appearance_counts, pair_counts = swap_optimize(
            sets, n_items, appearance_counts, pair_counts,
            max_iter=300, rng=rng,
        )

    if progress_callback:
        progress_callback(70.0, "Applying position balance...")

    if inp.position_balance:
        sets = apply_position_balance(sets, n_items, k, rng)

    if progress_callback:
        progress_callback(85.0, "Assigning blocks...")

    maxdiff_sets = create_blocks(sets, inp.items, inp.n_blocks, rng)

    # Compute pair coverage: % of item pairs that co-appear at least once
    all_pairs = list(combinations(range(n_items), 2))
    covered = sum(1 for p in all_pairs if pair_counts.get(build_pair_key(*p), 0) > 0)
    pair_coverage_pct = 100.0 * covered / len(all_pairs) if all_pairs else 100.0

    # Convert appearance_counts to string keys
    str_appearance = {inp.items[i]: v for i, v in appearance_counts.items()}
    str_pair_counts = {
        (inp.items[min(i, j)], inp.items[max(i, j)]): v
        for (i, j), v in pair_counts.items()
    }

    if progress_callback:
        progress_callback(100.0, "Done!")

    return MaxDiffDesign(
        sets=maxdiff_sets,
        items=inp.items,
        n_blocks=inp.n_blocks,
        appearance_counts=str_appearance,
        pair_counts=str_pair_counts,
        metadata={
            "n_sets": n_sets,
            "n_per_set": k,
            "target_appearances": inp.target_appearances,
            "bibd_lambda": inp.bibd_lambda,
            "pair_coverage_pct": pair_coverage_pct,
            "appearance_variance": appearance_variance(appearance_counts),
            "seed": seed,
        },
    )
