"""
tests/test_maxdiff_generator.py
--------------------------------
Unit tests for the MaxDiff / BIBD generator.
"""

import pytest
from itertools import combinations

from core.models import MaxDiffInput
from core.maxdiff_generator import (
    greedy_init,
    swap_optimize,
    apply_position_balance,
    generate_maxdiff_design,
    appearance_variance,
    build_pair_key,
    update_counts,
)
import numpy as np


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def standard_items():
    return [f"Item {i+1}" for i in range(12)]


@pytest.fixture
def standard_input(standard_items):
    return MaxDiffInput(
        items=standard_items,
        n_per_set=4,
        target_appearances=3,
        n_blocks=2,
        position_balance=True,
        pair_optimization=True,
    )


# ── Appearance variance ───────────────────────────────────────────────────────

class TestAppearanceVariance:
    def test_perfect_balance(self):
        counts = {i: 3 for i in range(10)}
        assert appearance_variance(counts) == 0.0

    def test_imbalanced(self):
        counts = {0: 1, 1: 5}
        assert appearance_variance(counts) > 0.0

    def test_empty(self):
        assert appearance_variance({}) == 0.0


# ── Pair key helper ───────────────────────────────────────────────────────────

class TestBuildPairKey:
    def test_canonical_order(self):
        assert build_pair_key(3, 1) == (1, 3)
        assert build_pair_key(1, 3) == (1, 3)

    def test_symmetric(self):
        assert build_pair_key(5, 2) == build_pair_key(2, 5)


# ── Update counts ─────────────────────────────────────────────────────────────

class TestUpdateCounts:
    def test_increment(self):
        app = {}; pair = {}
        update_counts([0, 1, 2], app, pair, delta=1)
        assert app == {0: 1, 1: 1, 2: 1}
        assert pair[(0, 1)] == 1
        assert pair[(0, 2)] == 1
        assert pair[(1, 2)] == 1

    def test_decrement(self):
        app = {0: 2, 1: 2}; pair = {(0, 1): 2}
        update_counts([0, 1], app, pair, delta=-1)
        assert app[0] == 1
        assert pair[(0, 1)] == 1


# ── Greedy initialization ─────────────────────────────────────────────────────

class TestGreedyInit:
    def test_correct_n_sets(self):
        rng = np.random.default_rng(0)
        sets, _, _ = greedy_init(n_items=12, n_sets=9, k=4, rng=rng)
        assert len(sets) == 9

    def test_correct_set_size(self):
        rng = np.random.default_rng(0)
        sets, _, _ = greedy_init(n_items=12, n_sets=9, k=4, rng=rng)
        assert all(len(s) == 4 for s in sets)

    def test_no_duplicates_within_set(self):
        rng = np.random.default_rng(0)
        sets, _, _ = greedy_init(n_items=12, n_sets=9, k=4, rng=rng)
        for s in sets:
            assert len(s) == len(set(s)), f"Duplicate items in set: {s}"

    def test_items_in_valid_range(self):
        n_items = 12
        rng = np.random.default_rng(0)
        sets, _, _ = greedy_init(n_items=n_items, n_sets=9, k=4, rng=rng)
        for s in sets:
            assert all(0 <= item < n_items for item in s)


# ── Full generation pipeline ──────────────────────────────────────────────────

class TestGenerateMaxDiffDesign:
    def test_returns_design(self, standard_input):
        design = generate_maxdiff_design(standard_input, seed=42)
        assert design is not None

    def test_correct_n_blocks(self, standard_input):
        design = generate_maxdiff_design(standard_input, seed=42)
        assert design.n_blocks == standard_input.n_blocks

    def test_all_items_appear(self, standard_input, standard_items):
        design = generate_maxdiff_design(standard_input, seed=42)
        all_shown = [item for s in design.sets for item in s.items]
        for item in standard_items:
            assert item in all_shown, f"Item '{item}' never shown"

    def test_appearance_counts_near_target(self, standard_input):
        design = generate_maxdiff_design(standard_input, seed=42)
        target = standard_input.target_appearances
        for item, count in design.appearance_counts.items():
            assert abs(count - target) <= 2, (
                f"Item '{item}' appears {count} times, expected ~{target}"
            )

    def test_set_size_correct(self, standard_input):
        design = generate_maxdiff_design(standard_input, seed=42)
        for s in design.sets:
            assert len(s.items) == standard_input.n_per_set

    def test_no_duplicates_within_set(self, standard_input):
        design = generate_maxdiff_design(standard_input, seed=42)
        for s in design.sets:
            assert len(s.items) == len(set(s.items)), (
                f"Duplicate items in set {s.set_number}"
            )

    def test_metadata_present(self, standard_input):
        design = generate_maxdiff_design(standard_input, seed=42)
        assert "pair_coverage_pct" in design.metadata
        assert "bibd_lambda" in design.metadata

    def test_pair_coverage_reasonable(self, standard_input):
        design = generate_maxdiff_design(standard_input, seed=42)
        pct = design.metadata["pair_coverage_pct"]
        assert pct > 30.0, f"Pair coverage too low: {pct:.1f}%"
