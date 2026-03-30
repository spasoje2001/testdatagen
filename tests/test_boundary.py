"""
Unit tests for Boundary Value Analysis (BVA) Strategy.

Covers:
  - Integer ranges (standard, min=0, negative)
  - Decimal ranges with precision
  - Date ranges
  - Datetime ranges
  - Ref count boundaries
  - Edge cases (tiny ranges, single-value ranges)
"""

from testdatagen.strategies.boundary import (
    generate_boundary_values,
    generate_count_boundary_values,
)


# ---------------------------------------------------------------------------
# Helper to extract just values from results
# ---------------------------------------------------------------------------

def values_only(results):
    return [r["value"] for r in results]


def valid_values(results):
    return [r["value"] for r in results if r["category"] == "valid"]


def invalid_values(results):
    return [r["value"] for r in results if r["category"] == "invalid"]


# ===========================================================================
# 1. Integer ranges
# ===========================================================================

class TestIntegerBoundaries:

    def test_standard_range(self):
        """range 18..120 -> [17, 18, 19, 119, 120, 121]"""
        results = generate_boundary_values("number", 18, 120, precision=0)
        vals = values_only(results)

        assert 17 in vals   # invalid below
        assert 18 in vals   # min
        assert 19 in vals   # min+1
        assert 119 in vals  # max-1
        assert 120 in vals  # max
        assert 121 in vals  # invalid above

    def test_valid_invalid_categories(self):
        results = generate_boundary_values("number", 18, 120, precision=0)

        assert set(invalid_values(results)) == {17, 121}
        assert 18 in valid_values(results)
        assert 120 in valid_values(results)

    def test_min_zero(self):
        """range 0..100 -> should still include -1 as invalid"""
        results = generate_boundary_values("number", 0, 100, precision=0)
        vals = values_only(results)

        assert -1 in vals
        assert 0 in vals
        assert 1 in vals
        assert 99 in vals
        assert 100 in vals
        assert 101 in vals

    def test_negative_range(self):
        """range -50..50"""
        results = generate_boundary_values("number", -50, 50, precision=0)
        vals = values_only(results)

        assert -51 in vals  # invalid below
        assert -50 in vals  # min
        assert -49 in vals  # min+1
        assert 49 in vals   # max-1
        assert 50 in vals   # max
        assert 51 in vals   # invalid above

    def test_tiny_range(self):
        """range 5..6 -> [4, 5, 6, 7] -- min+1 == max-1 == deduplicated"""
        results = generate_boundary_values("number", 5, 6, precision=0)
        vals = values_only(results)

        assert 4 in vals
        assert 5 in vals
        assert 6 in vals
        assert 7 in vals
        # No duplicates
        assert len(vals) == len(set(vals))

    def test_single_value_range(self):
        """range 10..10 -> [9, 10, 11]"""
        results = generate_boundary_values("number", 10, 10, precision=0)
        vals = values_only(results)

        assert 9 in vals
        assert 10 in vals
        assert 11 in vals
        assert len(vals) == len(set(vals))


# ===========================================================================
# 2. Decimal ranges with precision
# ===========================================================================

class TestDecimalBoundaries:

    def test_precision_2(self):
        """range 0.01..9999.99, precision=2 -> step=0.01"""
        results = generate_boundary_values("number", 0.01, 9999.99, precision=2)
        vals = values_only(results)

        assert 0.00 in vals    # invalid below (0.01 - 0.01)
        assert 0.01 in vals    # min
        assert 0.02 in vals    # min+step
        assert 9999.98 in vals # max-step
        assert 9999.99 in vals # max
        assert 10000.00 in vals  # invalid above

    def test_precision_1(self):
        """range 1.0..5.0, precision=1 -> step=0.1"""
        results = generate_boundary_values("number", 1.0, 5.0, precision=1)
        vals = values_only(results)

        assert 0.9 in vals
        assert 1.0 in vals
        assert 1.1 in vals
        assert 4.9 in vals
        assert 5.0 in vals
        assert 5.1 in vals

    def test_no_floating_point_drift(self):
        """Ensure values are properly rounded."""
        results = generate_boundary_values("number", 0.01, 0.05, precision=2)
        for r in results:
            if isinstance(r["value"], float):
                # Check that string representation doesn't have excess decimals
                assert len(str(r["value"]).split(".")[-1]) <= 2 or r["value"] == int(r["value"])


# ===========================================================================
# 3. Date ranges
# ===========================================================================

class TestDateBoundaries:

    def test_standard_date_range(self):
        """range 2020-01-01..2025-12-31"""
        results = generate_boundary_values("date", "2020-01-01", "2025-12-31")
        vals = values_only(results)

        assert "2019-12-31" in vals  # day before min
        assert "2020-01-01" in vals  # min
        assert "2020-01-02" in vals  # day after min
        assert "2025-12-30" in vals  # day before max
        assert "2025-12-31" in vals  # max
        assert "2026-01-01" in vals  # day after max

    def test_date_valid_invalid(self):
        results = generate_boundary_values("date", "2024-01-01", "2024-12-31")

        assert "2023-12-31" in invalid_values(results)
        assert "2025-01-01" in invalid_values(results)
        assert "2024-01-01" in valid_values(results)
        assert "2024-12-31" in valid_values(results)

    def test_short_date_range(self):
        """range 2024-03-01..2024-03-02 -- very tight range"""
        results = generate_boundary_values("date", "2024-03-01", "2024-03-02")
        vals = values_only(results)

        assert "2024-02-29" in vals  # day before min (2024 is leap year)
        assert "2024-03-01" in vals
        assert "2024-03-02" in vals
        assert "2024-03-03" in vals


# ===========================================================================
# 4. Datetime ranges
# ===========================================================================

class TestDatetimeBoundaries:

    def test_datetime_range(self):
        results = generate_boundary_values(
            "datetime", "2024-01-01T00:00:00", "2024-12-31T23:59:59"
        )
        vals = values_only(results)

        assert "2023-12-31T00:00:00" in vals  # invalid below
        assert "2024-01-01T00:00:00" in vals  # min
        assert "2024-01-02T00:00:00" in vals  # min+1day
        assert len(vals) == 6


# ===========================================================================
# 5. Ref count boundaries
# ===========================================================================

class TestCountBoundaries:

    def test_count_range(self):
        """count 1..10 -> [0, 1, 2, 9, 10, 11]"""
        results = generate_count_boundary_values(1, 10)
        vals = values_only(results)

        assert 0 in vals   # invalid below
        assert 1 in vals   # min
        assert 2 in vals   # min+1
        assert 9 in vals   # max-1
        assert 10 in vals  # max
        assert 11 in vals  # invalid above

    def test_count_min_zero(self):
        """count 0..5"""
        results = generate_count_boundary_values(0, 5)
        vals = values_only(results)

        assert -1 in vals
        assert 0 in vals
        assert 1 in vals
        assert 5 in vals
        assert 6 in vals


# ===========================================================================
# 6. Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_unsupported_type_returns_empty(self):
        """Non-range types like 'email' should return empty list."""
        results = generate_boundary_values("email", None, None)
        assert results == []

    def test_no_duplicates_in_results(self):
        """All results should have unique values."""
        results = generate_boundary_values("number", 1, 3, precision=0)
        vals = values_only(results)
        assert len(vals) == len(set(vals))

    def test_result_structure(self):
        """Each result should have 'value' and 'category' keys."""
        results = generate_boundary_values("number", 0, 100, precision=0)
        for r in results:
            assert "value" in r
            assert "category" in r
            assert r["category"] in ("valid", "invalid")