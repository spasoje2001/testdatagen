"""
Unit tests for Each-Used Combination Strategy.

Covers:
  - Every value appears at least once
  - Correct count (= max field size)
  - Reproducibility with seed
  - Recycling of shorter lists
  - Edge cases (single field, equal-length fields, single-value fields)
"""

from testdatagen.strategies.combination import each_used_combination, each_used_combination_count


# ===========================================================================
# 1. Every value appears at least once
# ===========================================================================

class TestEachValueAppears:

    def test_all_values_present_2_fields(self):
        """Every value from every field must appear in the results."""
        fields = {
            "age": [17, 18, 19, 64, 65],
            "status": ["active", "inactive", "banned"],
        }
        results = each_used_combination(fields, seed=42)

        ages = {r["age"] for r in results}
        statuses = {r["status"] for r in results}

        assert ages == {17, 18, 19, 64, 65}
        assert statuses == {"active", "inactive", "banned"}

    def test_all_values_present_4_fields(self):
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
            "d": ["p", "q", "r", "s"],
        }
        results = each_used_combination(fields, seed=42)

        assert {r["a"] for r in results} == {1, 2, 3, 4, 5}
        assert {r["b"] for r in results} == {"x", "y", "z"}
        assert {r["c"] for r in results} == {True, False}
        assert {r["d"] for r in results} == {"p", "q", "r", "s"}

    def test_all_values_present_asymmetric(self):
        """Field with 10 values, field with 2 values."""
        fields = {
            "big": list(range(10)),
            "small": ["a", "b"],
        }
        results = each_used_combination(fields, seed=42)

        assert {r["big"] for r in results} == set(range(10))
        assert {r["small"] for r in results} == {"a", "b"}


# ===========================================================================
# 2. Correct count (= max field size)
# ===========================================================================

class TestCorrectCount:

    def test_count_equals_max_field_size(self):
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
        }
        results = each_used_combination(fields, seed=42)
        assert len(results) == 5  # max(5, 3)

    def test_count_4_fields(self):
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
            "d": ["p", "q", "r", "s"],
        }
        results = each_used_combination(fields, seed=42)
        assert len(results) == 5  # max(5, 3, 2, 4)

    def test_count_equal_length_fields(self):
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y", "z"],
        }
        results = each_used_combination(fields, seed=42)
        assert len(results) == 3

    def test_count_function_matches(self):
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
        }
        assert each_used_combination_count(fields) == 5
        assert each_used_combination_count(fields) == len(
            each_used_combination(fields, seed=42)
        )


# ===========================================================================
# 3. Reproducibility with seed
# ===========================================================================

class TestReproducibility:

    def test_same_seed_same_results(self):
        fields = {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "z"],
            "c": [True, False],
        }
        run1 = each_used_combination(fields, seed=12345)
        run2 = each_used_combination(fields, seed=12345)
        assert run1 == run2

    def test_different_seed_different_order(self):
        """Different seeds should (almost certainly) produce different orderings."""
        fields = {
            "a": list(range(20)),
            "b": list(range(20)),
        }
        run1 = each_used_combination(fields, seed=1)
        run2 = each_used_combination(fields, seed=2)
        # Same values present, but different arrangement
        assert {r["a"] for r in run1} == {r["a"] for r in run2}
        # Extremely unlikely to be identical with different seeds and 20 values
        assert run1 != run2

    def test_no_seed_still_works(self):
        """seed=None should still produce valid results."""
        fields = {
            "a": [1, 2, 3],
            "b": ["x", "y"],
        }
        results = each_used_combination(fields, seed=None)
        assert len(results) == 3
        assert {r["a"] for r in results} == {1, 2, 3}
        assert {r["b"] for r in results}.issubset({"x", "y"})


# ===========================================================================
# 4. Recycling of shorter lists
# ===========================================================================

class TestRecycling:

    def test_shorter_list_values_recycled(self):
        """A 2-value field paired with a 5-value field: the 2-value field
        must appear in all 5 rows, meaning values get reused."""
        fields = {
            "big": [1, 2, 3, 4, 5],
            "small": ["a", "b"],
        }
        results = each_used_combination(fields, seed=42)

        small_values = [r["small"] for r in results]
        assert len(small_values) == 5  # padded to match big
        assert set(small_values) == {"a", "b"}  # both originals appear

    def test_single_value_field_repeated(self):
        """A field with 1 value appears in every row."""
        fields = {
            "many": [1, 2, 3, 4],
            "one": ["only"],
        }
        results = each_used_combination(fields, seed=42)
        assert all(r["one"] == "only" for r in results)
        assert len(results) == 4


# ===========================================================================
# 5. Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_single_field(self):
        fields = {"status": ["active", "inactive", "banned"]}
        results = each_used_combination(fields, seed=42)
        assert len(results) == 3
        assert {r["status"] for r in results} == {"active", "inactive", "banned"}

    def test_all_single_value_fields(self):
        """Every field has 1 value -> 1 combination."""
        fields = {
            "a": [1],
            "b": ["x"],
            "c": [True],
        }
        results = each_used_combination(fields, seed=42)
        assert len(results) == 1
        assert results[0] == {"a": 1, "b": "x", "c": True}

    def test_empty_field_returns_empty(self):
        fields = {"a": [1, 2], "b": []}
        results = each_used_combination(fields, seed=42)
        assert results == []

    def test_empty_dict_returns_empty(self):
        results = each_used_combination({}, seed=42)
        assert results == []

    def test_empty_field_count_zero(self):
        assert each_used_combination_count({"a": [1], "b": []}) == 0

    def test_empty_dict_count_zero(self):
        assert each_used_combination_count({}) == 0

    def test_returns_list_of_dicts(self):
        fields = {"x": [1, 2], "y": ["a", "b"]}
        results = each_used_combination(fields, seed=42)
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)

    def test_preserves_value_types(self):
        fields = {
            "a": [None, 42, "hello", True, 3.14],
            "b": ["only"],
        }
        results = each_used_combination(fields, seed=42)
        values_a = {r["a"] for r in results}
        assert None in values_a
        assert 42 in values_a
        assert "hello" in values_a
        assert 3.14 in values_a

    def test_all_field_names_present(self):
        fields = {"x": [1, 2, 3], "y": ["a"], "z": [True, False]}
        results = each_used_combination(fields, seed=42)
        for r in results:
            assert set(r.keys()) == {"x", "y", "z"}