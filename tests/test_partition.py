"""
Unit tests for Equivalence Partitioning (EP) Strategy.

Covers:
  - Number range partitioning (default and custom count)
  - Decimal precision
  - Date range partitioning
  - Datetime range partitioning
  - Enum types (each value = own partition)
  - Edge cases (single partition, single-value range)
"""

from testdatagen.strategies.partition import (
    generate_partition_values,
    generate_enum_partition_values,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def values_only(results):
    return [r["value"] for r in results]


# ===========================================================================
# 1. Number range partitioning
# ===========================================================================

class TestNumberPartitions:

    def test_default_3_partitions(self):
        """range 0..90, 3 partitions -> midpoints at 15, 45, 75"""
        results = generate_partition_values("number", 0, 90, num_partitions=3)
        vals = values_only(results)

        assert len(vals) == 3
        assert vals[0] == 15   # mid of [0, 30)
        assert vals[1] == 45   # mid of [30, 60)
        assert vals[2] == 75   # mid of [60, 90]

    def test_partition_count_matches(self):
        """Should return exactly N values for N partitions."""
        for n in [1, 2, 3, 5, 10]:
            results = generate_partition_values("number", 0, 100, num_partitions=n)
            assert len(results) == n

    def test_values_within_range(self):
        """All representative values must fall within [min, max]."""
        results = generate_partition_values("number", 10, 50, num_partitions=4)
        for r in results:
            assert 10 <= r["value"] <= 50

    def test_values_are_distinct(self):
        """No two partitions should produce the same representative."""
        results = generate_partition_values("number", 0, 100, num_partitions=5)
        vals = values_only(results)
        assert len(vals) == len(set(vals))

    def test_partitions_cover_range(self):
        """Partition boundaries should span from min to max."""
        results = generate_partition_values("number", 0, 100, num_partitions=4)
        # First partition starts at min
        assert results[0]["partition"][0] == 0
        # Last partition ends at max
        assert results[-1]["partition"][1] == 100

    def test_negative_range(self):
        """range -60..60, 3 partitions -> midpoints at -40, 0, 40"""
        # Partitions: [-60,-20), [-20,20), [20,60]
        # Midpoints: -40, 0, 40
        results = generate_partition_values("number", -60, 60, num_partitions=3)
        vals = values_only(results)

        assert len(vals) == 3
        assert vals[0] == -40
        assert vals[1] == 0
        assert vals[2] == 40


# ===========================================================================
# 2. Custom partition count
# ===========================================================================

class TestCustomPartitionCount:

    def test_2_partitions(self):
        """range 0..100, 2 partitions -> midpoints at 25, 75"""
        results = generate_partition_values("number", 0, 100, num_partitions=2)
        vals = values_only(results)

        assert vals[0] == 25
        assert vals[1] == 75

    def test_5_partitions(self):
        """range 0..100, 5 partitions -> midpoints at 10, 30, 50, 70, 90"""
        results = generate_partition_values("number", 0, 100, num_partitions=5)
        vals = values_only(results)

        assert len(vals) == 5
        assert vals[0] == 10
        assert vals[2] == 50
        assert vals[4] == 90

    def test_partition_count_zero_treated_as_one(self):
        """num_partitions=0 should be clamped to 1."""
        results = generate_partition_values("number", 0, 100, num_partitions=0)
        assert len(results) == 1

    def test_partition_count_negative_treated_as_one(self):
        """Negative partition count should be clamped to 1."""
        results = generate_partition_values("number", 0, 100, num_partitions=-3)
        assert len(results) == 1


# ===========================================================================
# 3. Decimal precision
# ===========================================================================

class TestDecimalPartitions:

    def test_precision_2(self):
        """range 0.00..1.00, 4 partitions, precision=2"""
        results = generate_partition_values("number", 0.00, 1.00,
                                            num_partitions=4, precision=2)
        vals = values_only(results)

        assert len(vals) == 4
        # mid of [0.00, 0.25) = 0.125 -> rounds to 0.12
        # mid of [0.25, 0.50) = 0.375 -> rounds to 0.38
        # mid of [0.50, 0.75) = 0.625 -> rounds to 0.62
        # mid of [0.75, 1.00] = 0.875 -> rounds to 0.88
        assert vals[0] == 0.12
        assert vals[1] == 0.38
        assert vals[2] == 0.62
        assert vals[3] == 0.88

    def test_precision_respected(self):
        """Values should not have more decimal places than precision."""
        results = generate_partition_values("number", 0.01, 9999.99,
                                            num_partitions=3, precision=2)
        for r in results:
            str_val = str(r["value"])
            if "." in str_val:
                decimals = len(str_val.split(".")[-1])
                assert decimals <= 2


# ===========================================================================
# 4. Date range partitioning
# ===========================================================================

class TestDatePartitions:

    def test_date_3_partitions(self):
        """365-day range, 3 partitions -> 3 midpoints spread across the year"""
        results = generate_partition_values("date", "2024-01-01", "2024-12-31",
                                            num_partitions=3)
        vals = values_only(results)

        assert len(vals) == 3
        # Midpoints should be roughly in the first, second, and third third
        # Total days = 365, step = ~121.67 days
        # Partition 1 mid: ~day 60 -> early March
        # Partition 2 mid: ~day 182 -> early July
        # Partition 3 mid: ~day 304 -> late October
        assert vals[0] < vals[1] < vals[2]
        assert vals[0].startswith("2024-03") or vals[0].startswith("2024-02")
        assert vals[2].startswith("2024-10") or vals[2].startswith("2024-11")

    def test_date_values_within_range(self):
        results = generate_partition_values("date", "2024-01-01", "2024-12-31",
                                            num_partitions=4)
        for r in results:
            assert "2024-01-01" <= r["value"] <= "2024-12-31"

    def test_date_partition_count(self):
        results = generate_partition_values("date", "2024-01-01", "2024-12-31",
                                            num_partitions=6)
        assert len(results) == 6

    def test_date_short_range(self):
        """3-day range, 3 partitions"""
        results = generate_partition_values("date", "2024-06-01", "2024-06-04",
                                            num_partitions=3)
        vals = values_only(results)
        assert len(vals) == 3


# ===========================================================================
# 5. Datetime partitions
# ===========================================================================

class TestDatetimePartitions:

    def test_datetime_basic(self):
        results = generate_partition_values("datetime",
                                            "2024-01-01T00:00:00",
                                            "2024-12-31T23:59:59",
                                            num_partitions=3)
        vals = values_only(results)
        assert len(vals) == 3
        assert vals[0] < vals[1] < vals[2]


# ===========================================================================
# 6. Enum types
# ===========================================================================

class TestEnumPartitions:

    def test_enum_returns_all_values(self):
        """Each enum value is its own partition."""
        results = generate_enum_partition_values(["active", "inactive", "banned"])
        vals = values_only(results)

        assert vals == ["active", "inactive", "banned"]

    def test_enum_partition_structure(self):
        """Each result should have value and partition tuple."""
        results = generate_enum_partition_values(["a", "b"])
        for r in results:
            assert "value" in r
            assert "partition" in r
            assert r["value"] == r["partition"][0] == r["partition"][1]

    def test_enum_single_value(self):
        results = generate_enum_partition_values(["only_one"])
        assert len(results) == 1
        assert results[0]["value"] == "only_one"

    def test_enum_many_values(self):
        vals = ["pending", "processing", "shipped", "delivered", "cancelled"]
        results = generate_enum_partition_values(vals)
        assert len(results) == 5
        assert values_only(results) == vals


# ===========================================================================
# 7. Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_single_partition(self):
        """1 partition -> midpoint of entire range."""
        results = generate_partition_values("number", 0, 100, num_partitions=1)
        assert len(results) == 1
        assert results[0]["value"] == 50

    def test_single_value_range(self):
        """range 42..42 -> just returns 42."""
        results = generate_partition_values("number", 42, 42, num_partitions=3)
        assert len(results) == 1
        assert results[0]["value"] == 42

    def test_single_day_date_range(self):
        """Same date for min and max."""
        results = generate_partition_values("date", "2024-06-15", "2024-06-15",
                                            num_partitions=3)
        assert len(results) == 1
        assert results[0]["value"] == "2024-06-15"

    def test_unsupported_type_returns_empty(self):
        results = generate_partition_values("email", None, None)
        assert results == []

    def test_result_structure(self):
        """Each result should have 'value' and 'partition' keys."""
        results = generate_partition_values("number", 0, 100, num_partitions=3)
        for r in results:
            assert "value" in r
            assert "partition" in r
            assert isinstance(r["partition"], tuple)
            assert len(r["partition"]) == 2