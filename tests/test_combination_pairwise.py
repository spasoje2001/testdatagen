"""
Unit tests for Pairwise (All-Pairs) Combination Strategy.

Covers:
  - All pairs covered
  - Size comparison to full Cartesian (should be much smaller for 3+ fields)
  - 2 fields (should equal full Cartesian)
  - 4+ fields (significant reduction)
  - Coverage tracking
  - Performance
  - Edge cases
"""

import time
from testdatagen.strategies.combination import (
    pairwise_combination,
    pairwise_coverage,
    full_combination_count,
)

# ---------------------------------------------------------------------------
# Helper: verify every pair of values is present in results
# ---------------------------------------------------------------------------

def assert_all_pairs_covered(field_values, results):
    """Check that every pair of values from any two fields appears
    in at least one result row."""
    field_names = list(field_values.keys())

    for i, name_i in enumerate(field_names):
        for j, name_j in enumerate(field_names):
            if j <= i:
                continue
            for vi in field_values[name_i]:
                for vj in field_values[name_j]:
                    found = any(
                        r[name_i] == vi and r[name_j] == vj
                        for r in results
                    )
                    assert found, (
                        f"Pair ({name_i}={vi}, {name_j}={vj}) not found "
                        f"in {len(results)} results"
                    )


# ===========================================================================
# 1. All pairs covered
# ===========================================================================

class TestAllPairsCovered:

    def test_3_fields(self):
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
            "c": [True, False],
        }
        results = pairwise_combination(fields, seed=42)
        assert_all_pairs_covered(fields, results)

    def test_4_fields(self):
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
            "d": ["p", "q", "r", "s"],
        }
        results = pairwise_combination(fields, seed=42)
        assert_all_pairs_covered(fields, results)

    def test_5_fields(self):
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
            "d": ["p", "q", "r", "s"],
            "e": ["m", "n", "o"],
        }
        results = pairwise_combination(fields, seed=42)
        assert_all_pairs_covered(fields, results)

    def test_coverage_function_reports_100(self):
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
            "c": [True, False],
        }
        results = pairwise_combination(fields, seed=42)
        cov = pairwise_coverage(fields, results)

        assert cov["coverage"] == 1.0
        assert cov["covered_pairs"] == cov["total_pairs"]
        assert len(cov["uncovered"]) == 0


# ===========================================================================
# 2. Size comparison to full Cartesian
# ===========================================================================

class TestSizeReduction:

    def test_3_fields_smaller_than_full(self):
        """3 fields: full = 30, pairwise should be significantly less."""
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
        }
        results = pairwise_combination(fields, seed=42)
        full = full_combination_count(fields)

        assert full == 30
        assert len(results) < full

    def test_4_fields_much_smaller_than_full(self):
        """4 fields: full = 120, pairwise should be ~20-25."""
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
            "d": ["p", "q", "r", "s"],
        }
        results = pairwise_combination(fields, seed=42)
        full = full_combination_count(fields)

        assert full == 120
        assert len(results) <= 30  # generous upper bound
        assert len(results) >= 20  # at least max(Ni*Nj) = 5*4 = 20

    def test_5_fields_drastic_reduction(self):
        """5 fields: full = 360, pairwise should be dramatically less."""
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
            "d": ["p", "q", "r", "s"],
            "e": ["m", "n", "o"],
        }
        results = pairwise_combination(fields, seed=42)
        full = full_combination_count(fields)

        assert full == 360
        assert len(results) < full
        assert len(results) <= 35  # should still be compact


# ===========================================================================
# 3. Two fields (pairwise = full)
# ===========================================================================

class TestTwoFields:

    def test_2_fields_equals_full(self):
        """With only 2 fields, pairwise must cover every combination = full."""
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
        }
        results = pairwise_combination(fields, seed=42)
        full = full_combination_count(fields)

        assert len(results) == full  # 5 * 3 = 15
        assert_all_pairs_covered(fields, results)

    def test_2_fields_small(self):
        fields = {
            "status": ["active", "inactive"],
            "role": ["admin", "user"],
        }
        results = pairwise_combination(fields, seed=42)
        assert len(results) == 4  # 2 * 2
        assert_all_pairs_covered(fields, results)


# ===========================================================================
# 4. Reproducibility
# ===========================================================================

class TestReproducibility:

    def test_same_seed_same_results(self):
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
        }
        run1 = pairwise_combination(fields, seed=99)
        run2 = pairwise_combination(fields, seed=99)
        assert run1 == run2

    def test_no_seed_still_works(self):
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
        }
        results = pairwise_combination(fields, seed=None)
        assert_all_pairs_covered(fields, results)


# ===========================================================================
# 5. Coverage tracking
# ===========================================================================

class TestCoverageTracking:

    def test_total_pairs_count(self):
        """Total pairs = sum of (|Fi| * |Fj|) for all field pairs."""
        fields = {
            "a": [1, 2, 3, 4, 5],  # 5
            "b": ["x", "y", "z"],    # 3
            "c": [True, False],      # 2
            "d": ["p", "q", "r", "s"],  # 4
        }
        results = pairwise_combination(fields, seed=42)
        cov = pairwise_coverage(fields, results)

        # Pairs: (5*3)+(5*2)+(5*4)+(3*2)+(3*4)+(2*4) = 15+10+20+6+12+8 = 71
        assert cov["total_pairs"] == 71
        assert cov["coverage"] == 1.0

    def test_partial_coverage_detection(self):
        """If we only provide some rows, coverage should be < 1.0."""
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
            "c": [True, False],
        }
        # Provide just one row
        partial = [{"a": 1, "b": "x", "c": True}]
        cov = pairwise_coverage(fields, partial)

        assert cov["coverage"] < 1.0
        assert cov["covered_pairs"] < cov["total_pairs"]
        assert len(cov["uncovered"]) > 0


# ===========================================================================
# 6. Performance
# ===========================================================================

class TestPerformance:

    def test_moderate_fields(self):
        """6 fields should complete quickly."""
        fields = {
            "a": list(range(5)),
            "b": list(range(4)),
            "c": list(range(3)),
            "d": list(range(4)),
            "e": list(range(3)),
            "f": list(range(2)),
        }
        start = time.time()
        results = pairwise_combination(fields, seed=42)
        elapsed = time.time() - start

        assert_all_pairs_covered(fields, results)
        full = full_combination_count(fields)
        assert len(results) < full
        assert elapsed < 5.0


# ===========================================================================
# 7. Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_single_field(self):
        fields = {"status": ["active", "inactive", "banned"]}
        results = pairwise_combination(fields, seed=42)
        assert len(results) == 3

    def test_all_single_value_fields(self):
        fields = {"a": [1], "b": ["x"], "c": [True]}
        results = pairwise_combination(fields, seed=42)
        assert len(results) == 1
        assert results[0] == {"a": 1, "b": "x", "c": True}

    def test_empty_field_returns_empty(self):
        fields = {"a": [1, 2], "b": []}
        results = pairwise_combination(fields, seed=42)
        assert results == []

    def test_empty_dict_returns_empty(self):
        results = pairwise_combination({}, seed=42)
        assert results == []

    def test_returns_list_of_dicts(self):
        fields = {"a": [1, 2], "b": ["x", "y"], "c": [True, False]}
        results = pairwise_combination(fields, seed=42)
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)

    def test_all_field_names_present(self):
        fields = {"x": [1, 2, 3], "y": ["a"], "z": [True, False]}
        results = pairwise_combination(fields, seed=42)
        for r in results:
            assert set(r.keys()) == {"x", "y", "z"}

    def test_preserves_value_types(self):
        fields = {
            "a": [None, 42, "hello"],
            "b": [True, False],
        }
        results = pairwise_combination(fields, seed=42)
        values_a = {r["a"] for r in results}
        assert None in values_a
        assert 42 in values_a
        assert "hello" in values_a

    def test_no_duplicate_rows(self):
        """All result rows should be unique."""
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
            "c": [True, False],
        }
        results = pairwise_combination(fields, seed=42)
        tuples = [tuple(sorted(r.items())) for r in results]
        assert len(tuples) == len(set(tuples))