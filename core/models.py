"""
core/models.py
--------------
Dataclasses that represent every domain object in the system.
Using dataclasses (not Pydantic) keeps the dependency footprint small
while still providing type hints and __repr__ for free.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


# ── Input models ───────────────────────────────────────────────────────────────

@dataclass
class Attribute:
    """A single conjoint attribute with its levels."""
    name: str
    levels: List[str]
    is_price: bool = False
    level_order: str = "none"  # "none" | "ascending" | "descending"

    @property
    def n_levels(self) -> int:
        return len(self.levels)

    @property
    def n_params(self) -> int:
        """Number of effects-coded parameters this attribute contributes."""
        return self.n_levels - 1


@dataclass
class Prohibition:
    """A forbidden combination of attribute levels."""
    attribute_a: str
    level_a: str
    attribute_b: str
    level_b: str

    def __str__(self) -> str:
        return f"{self.attribute_a}={self.level_a}  ✕  {self.attribute_b}={self.level_b}"


@dataclass
class CBCInput:
    """All inputs needed to generate a Choice-Based Conjoint design."""
    attributes: List[Attribute]
    n_tasks: int = 10
    n_alternatives: int = 3
    n_blocks: int = 4
    n_holdout: int = 2
    sample_size: int = 300
    include_none: bool = True
    include_holdout: bool = True
    dual_none: bool = False
    bayesian: bool = True
    prior_variance: float = 1.0
    fatigue_opt: bool = True
    prohibitions: List[Prohibition] = field(default_factory=list)

    @property
    def n_params(self) -> int:
        return sum(a.n_params for a in self.attributes)

    @property
    def full_factorial_size(self) -> int:
        result = 1
        for a in self.attributes:
            result *= a.n_levels
        return result

    @property
    def total_tasks(self) -> int:
        return self.n_tasks + (self.n_holdout if self.include_holdout else 0)


@dataclass
class MaxDiffInput:
    """All inputs needed to generate a MaxDiff (Best-Worst Scaling) design."""
    items: List[str]
    n_per_set: int = 4
    target_appearances: int = 3
    n_blocks: int = 2
    position_balance: bool = True
    pair_optimization: bool = True
    anchored: bool = False

    @property
    def n_items(self) -> int:
        return len(self.items)

    @property
    def n_sets(self) -> int:
        """Minimum sets needed to achieve target_appearances for all items."""
        import math
        return math.ceil(self.n_items * self.target_appearances / self.n_per_set)

    @property
    def bibd_lambda(self) -> float:
        """Target pair co-occurrence frequency (may be non-integer → near-BIBD)."""
        if self.n_items <= 1:
            return 0.0
        return self.target_appearances * (self.n_per_set - 1) / (self.n_items - 1)


# ── Output / result models ─────────────────────────────────────────────────────

@dataclass
class CBCTask:
    """One choice task shown to a respondent."""
    task_number: int
    block: int
    is_holdout: bool
    alternatives: List[Dict[str, str]]  # list of {attr_name: level_value}
    complexity_score: float = 0.0       # used for fatigue optimization ordering


@dataclass
class CBCDesign:
    """Complete CBC design: all blocks, tasks, and metadata."""
    tasks: List[CBCTask]
    attributes: List[Attribute]
    n_blocks: int
    n_tasks_per_block: int
    include_none: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_block(self, block: int) -> List[CBCTask]:
        return [t for t in self.tasks if t.block == block]

    def get_holdout_tasks(self) -> List[CBCTask]:
        return [t for t in self.tasks if t.is_holdout]

    @property
    def blocks(self) -> List[int]:
        return sorted(set(t.block for t in self.tasks))


@dataclass
class MaxDiffSet:
    """One MaxDiff set shown to a respondent."""
    set_number: int
    block: int
    items: List[str]       # items in display order


@dataclass
class MaxDiffDesign:
    """Complete MaxDiff design: all sets and metadata."""
    sets: List[MaxDiffSet]
    items: List[str]
    n_blocks: int
    appearance_counts: Dict[str, int] = field(default_factory=dict)
    pair_counts: Dict[tuple, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_block(self, block: int) -> List[MaxDiffSet]:
        return [s for s in self.sets if s.block == block]

    @property
    def blocks(self) -> List[int]:
        return sorted(set(s.block for s in self.sets))


# ── Diagnostics model ─────────────────────────────────────────────────────────

@dataclass
class LevelBalance:
    attribute_name: str
    counts: Dict[str, int]
    expected_count: float
    chi2_stat: float
    is_balanced: bool


@dataclass
class DiagnosticsReport:
    """Statistical diagnostics report for a generated design."""
    study_type: str                         # "CBC" or "MaxDiff"
    d_efficiency: float                     # Bayesian D-efficiency %
    level_balance: List[LevelBalance]       # per-attribute balance
    max_attr_correlation: float             # max pairwise Spearman ρ
    correlation_matrix: Any                 # pandas DataFrame
    overlap_pct: float                      # % tasks with repeated levels (CBC only)
    expected_se: float                      # approx SE per parameter
    appearance_variance: float              # MaxDiff only: variance in item appearances
    pair_coverage_pct: float               # MaxDiff only: % pairs that co-appear
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def overall_grade(self) -> str:
        if self.d_efficiency >= 80 and self.max_attr_correlation < 0.10:
            return "Excellent"
        elif self.d_efficiency >= 65:
            return "Acceptable"
        else:
            return "Poor — regenerate"
