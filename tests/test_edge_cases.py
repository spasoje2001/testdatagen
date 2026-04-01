"""
Unit tests for Edge Case Generation Strategy.

Covers:
  - null generation
  - empty generation
  - invalid format per type
  - special (custom) values
  - enum coverage: all
  - combinations of include values
  - edge cases (empty inputs, unknown types)
"""

from testdatagen.strategies.edge_cases import (
    generate_edge_cases,
    generate_enum_coverage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def values_only(results):
    return [r["value"] for r in results]


def edge_types(results):
    return [r["edge_type"] for r in results]


# ===========================================================================
# 1. Null generation
# ===========================================================================

class TestNullGeneration:

    def test_null_included(self):
        results = generate_edge_cases("email", include_values=["null"])
        assert None in values_only(results)

    def test_null_edge_type(self):
        results = generate_edge_cases("email", include_values=["null"])
        null_cases = [r for r in results if r["edge_type"] == "null"]
        assert len(null_cases) == 1
        assert null_cases[0]["value"] is None

    def test_null_not_included_when_absent(self):
        results = generate_edge_cases("email", include_values=["empty"])
        assert None not in values_only(results)


# ===========================================================================
# 2. Empty generation
# ===========================================================================

class TestEmptyGeneration:

    def test_empty_included(self):
        results = generate_edge_cases("email", include_values=["empty"])
        assert "" in values_only(results)

    def test_empty_edge_type(self):
        results = generate_edge_cases("string", include_values=["empty"])
        empty_cases = [r for r in results if r["edge_type"] == "empty"]
        assert len(empty_cases) == 1
        assert empty_cases[0]["value"] == ""

    def test_empty_not_included_when_absent(self):
        results = generate_edge_cases("email", include_values=["null"])
        assert "" not in values_only(results)


# ===========================================================================
# 3. Invalid format per type
# ===========================================================================

class TestInvalidGeneration:

    def test_invalid_email(self):
        results = generate_edge_cases("email", include_values=["invalid"])
        vals = values_only(results)
        assert "invalid-email-format" in vals

    def test_invalid_url(self):
        results = generate_edge_cases("url", include_values=["invalid"])
        vals = values_only(results)
        assert "not-a-valid-url" in vals

    def test_invalid_uuid(self):
        results = generate_edge_cases("uuid", include_values=["invalid"])
        vals = values_only(results)
        assert "not-a-uuid" in vals

    def test_invalid_phone(self):
        results = generate_edge_cases("phone", include_values=["invalid"])
        vals = values_only(results)
        assert "123" in vals

    def test_invalid_date(self):
        results = generate_edge_cases("date", include_values=["invalid"])
        vals = values_only(results)
        assert "not-a-date" in vals

    def test_invalid_number(self):
        results = generate_edge_cases("number", include_values=["invalid"])
        vals = values_only(results)
        assert "NaN" in vals

    def test_invalid_unknown_type_fallback(self):
        """Unknown types get generic 'INVALID' string."""
        results = generate_edge_cases("somethingWeird", include_values=["invalid"])
        vals = values_only(results)
        assert "INVALID" in vals

    def test_invalid_edge_type(self):
        results = generate_edge_cases("email", include_values=["invalid"])
        invalid_cases = [r for r in results if r["edge_type"] == "invalid"]
        assert len(invalid_cases) == 1


# ===========================================================================
# 4. Special values
# ===========================================================================

class TestSpecialValues:

    def test_special_numbers(self):
        results = generate_edge_cases("number", special_values=[0, 1, 999, 1000])
        vals = values_only(results)
        assert vals == [0, 1, 999, 1000]

    def test_special_edge_type(self):
        results = generate_edge_cases("number", special_values=[42])
        assert all(r["edge_type"] == "special" for r in results)

    def test_special_strings(self):
        results = generate_edge_cases("string", special_values=["x" * 1000, "a"])
        vals = values_only(results)
        assert "x" * 1000 in vals
        assert "a" in vals

    def test_special_combined_with_include(self):
        """Special values should appear alongside include values."""
        results = generate_edge_cases(
            "number",
            include_values=["null"],
            special_values=[0, -1],
        )
        vals = values_only(results)
        assert None in vals
        assert 0 in vals
        assert -1 in vals


# ===========================================================================
# 5. Enum coverage: all
# ===========================================================================

class TestEnumCoverage:

    def test_all_values_present(self):
        results = generate_enum_coverage(["active", "inactive", "banned"])
        vals = values_only(results)
        assert vals == ["active", "inactive", "banned"]

    def test_edge_type_is_enum_coverage(self):
        results = generate_enum_coverage(["a", "b"])
        assert all(r["edge_type"] == "enum_coverage" for r in results)

    def test_single_enum_value(self):
        results = generate_enum_coverage(["only"])
        assert len(results) == 1
        assert results[0]["value"] == "only"

    def test_many_enum_values(self):
        vals = ["pending", "processing", "shipped", "delivered", "cancelled"]
        results = generate_enum_coverage(vals)
        assert len(results) == 5
        assert values_only(results) == vals

    def test_preserves_order(self):
        vals = ["z", "a", "m"]
        results = generate_enum_coverage(vals)
        assert values_only(results) == ["z", "a", "m"]


# ===========================================================================
# 6. Combined include values
# ===========================================================================

class TestCombinedIncludes:

    def test_all_three_includes(self):
        """include: [null, empty, invalid] produces 3 cases."""
        results = generate_edge_cases(
            "email",
            include_values=["null", "empty", "invalid"],
        )
        vals = values_only(results)
        assert None in vals
        assert "" in vals
        assert "invalid-email-format" in vals
        assert len(results) == 3

    def test_order_is_null_empty_invalid(self):
        """Output order should follow: null, empty, invalid."""
        results = generate_edge_cases(
            "url",
            include_values=["null", "empty", "invalid"],
        )
        types = edge_types(results)
        assert types == ["null", "empty", "invalid"]

    def test_all_includes_plus_special(self):
        results = generate_edge_cases(
            "number",
            include_values=["null", "empty", "invalid"],
            special_values=[0, 999],
        )
        assert len(results) == 5
        types = edge_types(results)
        assert types == ["null", "empty", "invalid", "special", "special"]


# ===========================================================================
# 7. Edge cases (no pun intended)
# ===========================================================================

class TestMetaEdgeCases:

    def test_no_include_no_special_returns_empty(self):
        results = generate_edge_cases("email")
        assert results == []

    def test_empty_include_list(self):
        results = generate_edge_cases("email", include_values=[])
        assert results == []

    def test_empty_special_list(self):
        results = generate_edge_cases("email", special_values=[])
        assert results == []

    def test_result_structure(self):
        """Each result should have 'value' and 'edge_type' keys."""
        results = generate_edge_cases(
            "email",
            include_values=["null", "empty", "invalid"],
            special_values=[42],
        )
        for r in results:
            assert "value" in r
            assert "edge_type" in r
            assert r["edge_type"] in ("null", "empty", "invalid", "special")