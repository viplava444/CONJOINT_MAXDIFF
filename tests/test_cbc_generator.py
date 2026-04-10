"""
tests/test_cbc_generator.py
----------------------------
Unit tests for the CBC design generator.

Run with: pytest tests/ -v
"""

import math
import pytest
import numpy as np

from core.models import Attribute, CBCInput, Prohibition
from core.cbc_generator import (
    effects_code,
    profile_to_vector,
    violates_prohibitions,
    compute_bayesian_d_efficiency,
    random_design,
    generate_cbc_design,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_attrs():
    return [
        Attribute("Brand", ["A", "B", "C"], is_price=False),
        Attribute("Price", ["$10", "$20", "$30"], is_price=True),
    ]


@pytest.fixture
def simple_input(simple_attrs):
    return CBCInput(
        attributes=simple_attrs,
        n_tasks=6,
        n_alternatives=2,
        n_blocks=2,
        n_holdout=1,
        sample_size=100,
        include_none=False,
        include_holdout=True,
        bayesian=False,  # faster for tests
        prior_variance=1.0,
    )


# ── Effects coding ────────────────────────────────────────────────────────────

class TestEffectsCoding:
    def test_non_reference_level(self):
        code = effects_code(0, 3)
        assert code == [1.0, 0.0]

    def test_second_level(self):
        code = effects_code(1, 3)
        assert code == [0.0, 1.0]

    def test_reference_level(self):
        """Last level is coded as all -1."""
        code = effects_code(2, 3)
        assert code == [-1.0, -1.0]

    def test_binary_attribute(self):
        assert effects_code(0, 2) == [1.0]
        assert effects_code(1, 2) == [-1.0]

    def test_length(self):
        for n in range(2, 7):
            code = effects_code(0, n)
            assert len(code) == n - 1


class TestProfileToVector:
    def test_vector_length(self, simple_attrs):
        profile = [0, 1]  # Brand=A, Price=$20
        vec = profile_to_vector(profile, simple_attrs)
        # Brand: 3 levels → 2 params; Price: 3 levels → 2 params → total 4
        assert len(vec) == 4

    def test_values(self, simple_attrs):
        profile = [0, 2]  # Brand=A (level 0), Price=$30 (reference level 2)
        vec = profile_to_vector(profile, simple_attrs)
        # Brand=A → [1, 0]; Price=$30 (ref) → [-1, -1]
        np.testing.assert_array_equal(vec, [1.0, 0.0, -1.0, -1.0])


# ── Prohibition checking ──────────────────────────────────────────────────────

class TestProhibitions:
    def test_no_prohibition(self, simple_attrs):
        profile = [0, 0]
        assert not violates_prohibitions(profile, simple_attrs, [])

    def test_prohibited_combination(self, simple_attrs):
        prohib = [Prohibition("Brand", "A", "Price", "$10")]
        profile = [0, 0]  # Brand=A, Price=$10
        assert violates_prohibitions(profile, simple_attrs, prohib)

    def test_non_prohibited_combination(self, simple_attrs):
        prohib = [Prohibition("Brand", "A", "Price", "$10")]
        profile = [0, 1]  # Brand=A, Price=$20 — not prohibited
        assert not violates_prohibitions(profile, simple_attrs, prohib)

    def test_unknown_attribute_ignored(self, simple_attrs):
        prohib = [Prohibition("Color", "Red", "Price", "$10")]
        profile = [0, 0]
        assert not violates_prohibitions(profile, simple_attrs, prohib)


# ── D-efficiency ──────────────────────────────────────────────────────────────

class TestDEfficiency:
    def test_returns_float(self, simple_attrs):
        rng = np.random.default_rng(42)
        design = random_design(4, 2, simple_attrs, [], rng)
        d_eff = compute_bayesian_d_efficiency(
            design, simple_attrs, prior_variance=1.0, n_monte_carlo=10, rng=rng
        )
        assert isinstance(d_eff, float)

    def test_in_valid_range(self, simple_attrs):
        rng = np.random.default_rng(42)
        design = random_design(6, 2, simple_attrs, [], rng)
        d_eff = compute_bayesian_d_efficiency(
            design, simple_attrs, prior_variance=1.0, n_monte_carlo=20, rng=rng
        )
        assert 0.0 <= d_eff <= 100.0

    def test_empty_design_returns_zero(self, simple_attrs):
        d_eff = compute_bayesian_d_efficiency([], simple_attrs)
        assert d_eff == 0.0


# ── Random design ─────────────────────────────────────────────────────────────

class TestRandomDesign:
    def test_shape(self, simple_attrs):
        rng = np.random.default_rng(0)
        design = random_design(5, 3, simple_attrs, [], rng)
        assert len(design) == 5
        assert all(len(task) == 3 for task in design)
        assert all(len(alt) == len(simple_attrs) for task in design for alt in task)

    def test_levels_in_range(self, simple_attrs):
        rng = np.random.default_rng(0)
        design = random_design(4, 2, simple_attrs, [], rng)
        for task in design:
            for alt in task:
                for attr_idx, level_idx in enumerate(alt):
                    assert 0 <= level_idx < simple_attrs[attr_idx].n_levels


# ── Full generation pipeline ──────────────────────────────────────────────────

class TestGenerateCBCDesign:
    def test_returns_design(self, simple_input):
        design = generate_cbc_design(simple_input, seed=42)
        assert design is not None

    def test_correct_n_blocks(self, simple_input):
        design = generate_cbc_design(simple_input, seed=42)
        assert design.n_blocks == simple_input.n_blocks

    def test_all_blocks_present(self, simple_input):
        design = generate_cbc_design(simple_input, seed=42)
        blocks_found = set(t.block for t in design.tasks)
        assert blocks_found == set(range(1, simple_input.n_blocks + 1))

    def test_holdout_tasks_present(self, simple_input):
        design = generate_cbc_design(simple_input, seed=42)
        holdout_tasks = design.get_holdout_tasks()
        assert len(holdout_tasks) > 0

    def test_no_out_of_range_levels(self, simple_input):
        design = generate_cbc_design(simple_input, seed=42)
        level_maps = {a.name: a.levels for a in design.attributes}
        for task in design.tasks:
            for alt in task.alternatives:
                for attr_name, level_val in alt.items():
                    assert level_val in level_maps[attr_name], (
                        f"Level '{level_val}' not in attribute '{attr_name}'"
                    )

    def test_d_efficiency_in_metadata(self, simple_input):
        design = generate_cbc_design(simple_input, seed=42)
        assert "d_efficiency" in design.metadata
        assert 0 <= design.metadata["d_efficiency"] <= 100
