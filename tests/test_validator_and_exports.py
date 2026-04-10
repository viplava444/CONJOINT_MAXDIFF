"""
tests/test_validator_and_exports.py
------------------------------------
Unit tests for the statistical validator and export functions.
"""

import json
import pytest
import pandas as pd

from core.models import Attribute, CBCInput, MaxDiffInput
from core.cbc_generator import generate_cbc_design
from core.maxdiff_generator import generate_maxdiff_design
from core.validator import validate_cbc, validate_maxdiff
from exports.exporters import (
    cbc_to_dataframe, maxdiff_to_dataframe,
    export_cbc_csv, export_cbc_json,
    export_maxdiff_csv, export_maxdiff_json,
    export_qualtrics_csv, export_sawtooth_csv,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cbc_design_and_input():
    attrs = [
        Attribute("Brand", ["A", "B", "C"]),
        Attribute("Price", ["$10", "$20", "$30"], is_price=True),
        Attribute("Feature", ["Yes", "No"]),
    ]
    inp = CBCInput(
        attributes=attrs,
        n_tasks=6, n_alternatives=2, n_blocks=2,
        n_holdout=1, sample_size=100,
        include_none=True, include_holdout=True,
        bayesian=False,
    )
    design = generate_cbc_design(inp, seed=0)
    return design, inp


@pytest.fixture(scope="module")
def maxdiff_design_and_input():
    items = [f"Item {i}" for i in range(10)]
    inp = MaxDiffInput(items=items, n_per_set=4, target_appearances=3, n_blocks=2)
    design = generate_maxdiff_design(inp, seed=0)
    return design, inp


# ── Validator: CBC ────────────────────────────────────────────────────────────

class TestValidateCBC:
    def test_returns_report(self, cbc_design_and_input):
        design, inp = cbc_design_and_input
        report = validate_cbc(design, inp)
        assert report is not None

    def test_d_efficiency_range(self, cbc_design_and_input):
        design, inp = cbc_design_and_input
        report = validate_cbc(design, inp)
        assert 0.0 <= report.d_efficiency <= 100.0

    def test_level_balance_for_all_attrs(self, cbc_design_and_input):
        design, inp = cbc_design_and_input
        report = validate_cbc(design, inp)
        balance_names = {b.attribute_name for b in report.level_balance}
        attr_names = {a.name for a in inp.attributes}
        assert attr_names == balance_names

    def test_overlap_in_range(self, cbc_design_and_input):
        design, inp = cbc_design_and_input
        report = validate_cbc(design, inp)
        assert 0.0 <= report.overlap_pct <= 100.0

    def test_correlation_matrix_shape(self, cbc_design_and_input):
        design, inp = cbc_design_and_input
        report = validate_cbc(design, inp)
        n = len(inp.attributes)
        if not report.correlation_matrix.empty:
            assert report.correlation_matrix.shape == (n, n)

    def test_overall_grade_string(self, cbc_design_and_input):
        design, inp = cbc_design_and_input
        report = validate_cbc(design, inp)
        assert report.overall_grade in ["Excellent", "Acceptable", "Poor — regenerate"]


# ── Validator: MaxDiff ────────────────────────────────────────────────────────

class TestValidateMaxDiff:
    def test_returns_report(self, maxdiff_design_and_input):
        design, inp = maxdiff_design_and_input
        report = validate_maxdiff(design, inp)
        assert report is not None

    def test_d_efficiency_range(self, maxdiff_design_and_input):
        design, inp = maxdiff_design_and_input
        report = validate_maxdiff(design, inp)
        assert 0.0 <= report.d_efficiency <= 100.0

    def test_pair_coverage_range(self, maxdiff_design_and_input):
        design, inp = maxdiff_design_and_input
        report = validate_maxdiff(design, inp)
        assert 0.0 <= report.pair_coverage_pct <= 100.0


# ── Exporters: CBC ────────────────────────────────────────────────────────────

class TestCBCExports:
    def test_csv_is_bytes(self, cbc_design_and_input):
        design, _ = cbc_design_and_input
        data = export_cbc_csv(design)
        assert isinstance(data, bytes)

    def test_csv_has_header(self, cbc_design_and_input):
        design, _ = cbc_design_and_input
        csv_str = export_cbc_csv(design).decode()
        assert "Block" in csv_str
        assert "Task" in csv_str
        assert "Alternative" in csv_str

    def test_json_parses(self, cbc_design_and_input):
        design, _ = cbc_design_and_input
        data = export_cbc_json(design)
        parsed = json.loads(data)
        assert parsed["study_type"] == "CBC"
        assert "blocks" in parsed

    def test_to_dataframe_shape(self, cbc_design_and_input):
        design, inp = cbc_design_and_input
        df = cbc_to_dataframe(design)
        assert isinstance(df, pd.DataFrame)
        assert "Block" in df.columns
        assert "Task" in df.columns

    def test_qualtrics_csv_format(self, cbc_design_and_input):
        design, _ = cbc_design_and_input
        csv_str = export_qualtrics_csv(design).decode()
        assert "QualticsBlock" in csv_str
        assert "TaskNum" in csv_str

    def test_sawtooth_csv_numeric(self, cbc_design_and_input):
        design, _ = cbc_design_and_input
        csv_str = export_sawtooth_csv(design).decode()
        assert "Version" in csv_str
        assert "Concept" in csv_str
        # Attribute columns should contain integers only (not level strings)
        df = pd.read_csv(__import__("io").StringIO(csv_str))
        for col in df.columns[3:]:  # skip Version, Task, Concept
            assert df[col].dtype in ["int64", "float64"], (
                f"Column '{col}' should be numeric in Sawtooth export"
            )


# ── Exporters: MaxDiff ────────────────────────────────────────────────────────

class TestMaxDiffExports:
    def test_csv_is_bytes(self, maxdiff_design_and_input):
        design, _ = maxdiff_design_and_input
        data = export_maxdiff_csv(design)
        assert isinstance(data, bytes)

    def test_csv_columns(self, maxdiff_design_and_input):
        design, _ = maxdiff_design_and_input
        csv_str = export_maxdiff_csv(design).decode()
        assert "Block" in csv_str
        assert "Set" in csv_str
        assert "Position" in csv_str
        assert "Item" in csv_str

    def test_json_parses(self, maxdiff_design_and_input):
        design, _ = maxdiff_design_and_input
        data = export_maxdiff_json(design)
        parsed = json.loads(data)
        assert parsed["study_type"] == "MaxDiff"
        assert "items" in parsed
