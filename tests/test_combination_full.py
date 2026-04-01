"""
Unit tests for Full Combination Strategy (Cartesian Product).

Covers:
  - 2-field combinations
  - 4-field combinations
  - generate limit
  - coverage count tracking
  - performance with large value sets
  - edge cases (empty fields, single field, single value)
"""

import time
from testdatagen.strategies.combination import full_combination, full_combination_count


# ===========================================================================
# 1. Two-field combinations
# ===========================================================================

class TestTwoFieldCombinations:

    def test_basic_2x2(self):
        """2 fields, 2 values each -> 4 combinations."""
        fields = {
            "status": ["active", "inactive"],
            "role": ["admin", "user"],
        }
        results = list(full_combination(fields))

        assert len(results) == 4
        assert {"status": "active", "role": "admin"} in results
        assert {"status": "active", "role": "user"} in results
        assert {"status": "inactive", "role": "admin"} in results
        assert {"status": "inactive", "role": "user"} in results

    def test_asymmetric_5x3(self):
        """5 x 3 -> 15 combinations."""
        fields = {
            "age": [17, 18, 19, 64, 65],
            "status": ["active", "inactive", "banned"],
        }
        results = list(full_combination(fields))
        assert len(results) == 15

    def test_all_field_names_present(self):
        """Every result dict should have all field names as keys."""
        fields = {
            "x": [1, 2, 3],
            "y": ["a", "b"],
        }
        results = list(full_combination(fields))
        for r in results:
            assert set(r.keys()) == {"x", "y"}

    def test_no_duplicate_combinations(self):
        """All combinations should be unique."""
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y", "z"],
        }
        results = list(full_combination(fields))
        tuples = [tuple(sorted(r.items())) for r in results]
        assert len(tuples) == len(set(tuples))


# ===========================================================================
# 2. Four-field combinations
# ===========================================================================

class TestFourFieldCombinations:

    def test_4_fields_product(self):
        """5 x 3 x 2 x 4 = 120 combinations."""
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
            "d": ["p", "q", "r", "s"],
        }
        results = list(full_combination(fields))
        assert len(results) == 120

    def test_4_fields_all_unique(self):
        fields = {
            "a": [1, 2],
            "b": ["x", "y"],
            "c": [True, False],
            "d": [10, 20],
        }
        results = list(full_combination(fields))
        assert len(results) == 16
        tuples = [tuple(sorted(r.items())) for r in results]
        assert len(set(tuples)) == 16

    def test_specific_combo_exists(self):
        """Verify a specific combination is present in the output."""
        fields = {
            "age": [18, 65],
            "status": ["active", "banned"],
            "role": ["admin", "user"],
            "verified": [True, False],
        }
        results = list(full_combination(fields))
        target = {"age": 65, "status": "banned", "role": "admin", "verified": False}
        assert target in results


# ===========================================================================
# 3. Generate limit
# ===========================================================================

class TestGenerateLimit:

    def test_limit_less_than_total(self):
        """Limit 5 on a 15-combo product -> exactly 5."""
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
        }
        results = list(full_combination(fields, limit=5))
        assert len(results) == 5

    def test_limit_greater_than_total(self):
        """Limit 100 on a 6-combo product -> all 6."""
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
        }
        results = list(full_combination(fields, limit=100))
        assert len(results) == 6

    def test_limit_equal_to_total(self):
        """Limit exactly matches total -> all produced."""
        fields = {
            "a": [1, 2],
            "b": ["x", "y"],
        }
        results = list(full_combination(fields, limit=4))
        assert len(results) == 4

    def test_limit_one(self):
        """Limit 1 -> exactly one combination."""
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y", "z"],
        }
        results = list(full_combination(fields, limit=1))
        assert len(results) == 1

    def test_limit_zero(self):
        """Limit 0 -> no combinations."""
        fields = {
            "a": [1, 2],
            "b": ["x", "y"],
        }
        results = list(full_combination(fields, limit=0))
        assert len(results) == 0

    def test_limit_none_means_all(self):
        """No limit -> all combinations."""
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
        }
        results = list(full_combination(fields, limit=None))
        assert len(results) == 6


# ===========================================================================
# 4. Coverage count tracking
# ===========================================================================

class TestCoverageCount:

    def test_count_matches_product(self):
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
        }
        assert full_combination_count(fields) == 6

    def test_count_4_fields(self):
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
            "d": ["p", "q", "r", "s"],
        }
        assert full_combination_count(fields) == 120

    def test_count_vs_generated(self):
        """Count should match actual generated count when no limit."""
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
            "c": [True, False],
        }
        total = full_combination_count(fields)
        generated = list(full_combination(fields))
        assert total == len(generated)

    def test_coverage_ratio_with_limit(self):
        """Demonstrate coverage tracking: generated / total."""
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
        }
        total = full_combination_count(fields)
        generated = list(full_combination(fields, limit=10))
        coverage = len(generated) / total
        assert total == 15
        assert len(generated) == 10
        assert abs(coverage - 10 / 15) < 0.001


# ===========================================================================
# 5. Performance with large value sets
# ===========================================================================

class TestPerformance:

    def test_generator_is_lazy(self):
        """Should not materialize all combos when using limit."""
        fields = {
            "a": list(range(100)),
            "b": list(range(100)),
            "c": list(range(100)),
        }
        # 100^3 = 1,000,000 total -- but we only take 10
        start = time.time()
        results = list(full_combination(fields, limit=10))
        elapsed = time.time() - start

        assert len(results) == 10
        assert elapsed < 1.0  # Should be near-instant

    def test_large_count_calculation(self):
        """Count should work instantly even for huge products."""
        fields = {
            "a": list(range(1000)),
            "b": list(range(1000)),
            "c": list(range(100)),
        }
        start = time.time()
        total = full_combination_count(fields)
        elapsed = time.time() - start

        assert total == 1000 * 1000 * 100
        assert elapsed < 0.1


# ===========================================================================
# 6. Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_single_field(self):
        """One field -> each value is its own combination."""
        fields = {"status": ["active", "inactive", "banned"]}
        results = list(full_combination(fields))
        assert len(results) == 3
        assert results[0] == {"status": "active"}

    def test_single_value_per_field(self):
        """Each field has 1 value -> exactly 1 combination."""
        fields = {
            "a": [1],
            "b": ["x"],
            "c": [True],
        }
        results = list(full_combination(fields))
        assert len(results) == 1
        assert results[0] == {"a": 1, "b": "x", "c": True}

    def test_empty_field_values(self):
        """A field with no values -> no combinations possible."""
        fields = {
            "a": [1, 2],
            "b": [],
        }
        results = list(full_combination(fields))
        assert len(results) == 0

    def test_empty_dict(self):
        """No fields -> no combinations."""
        results = list(full_combination({}))
        assert len(results) == 0

    def test_empty_dict_count(self):
        assert full_combination_count({}) == 0

    def test_empty_field_count(self):
        fields = {"a": [1, 2], "b": []}
        assert full_combination_count(fields) == 0

    def test_yields_dicts_not_tuples(self):
        """Output should be dicts, not raw tuples."""
        fields = {"x": [1], "y": [2]}
        results = list(full_combination(fields))
        assert isinstance(results[0], dict)

    def test_preserves_value_types(self):
        """None, booleans, strings, numbers should pass through unchanged."""
        fields = {
            "a": [None, 42, "hello", True, 3.14],
            "b": ["only"],
        }
        results = list(full_combination(fields))
        values_a = [r["a"] for r in results]
        assert None in values_a
        assert 42 in values_a
        assert "hello" in values_a
        assert True in values_a
        assert 3.14 in values_a