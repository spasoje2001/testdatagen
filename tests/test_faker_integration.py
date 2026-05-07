"""
Unit tests for testdatagen/generators/faker_integration.py  (#8)

Run with:
    pytest tests/test_faker_integration.py -v
"""

import re
import uuid
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from testdatagen.generators.faker_integration import FakerTypeMapper


# ---------------------------------------------------------------------------
# Mock helpers — use _type_class_name / _constraint_name so the production
# code can distinguish mock objects from real textX objects by attribute
# rather than by class name (SimpleNamespace always reports "SimpleNamespace")
# ---------------------------------------------------------------------------

def make_simple_type(name: str):
    obj = SimpleNamespace(name=name)
    obj._type_class_name = "SimpleType"
    return obj


def make_enum_type(values):
    obj = SimpleNamespace(values=values)
    obj._type_class_name = "EnumType"
    return obj


def make_ref_type(entity_name: str):
    obj = SimpleNamespace(entity=entity_name)
    obj._type_class_name = "RefType"
    return obj


def make_range_constraint(min_val, max_val):
    obj = SimpleNamespace(min=min_val, max=max_val)
    obj._constraint_name = "RangeConstraint"
    return obj


def make_precision_constraint(value: int):
    obj = SimpleNamespace(value=value)
    obj._constraint_name = "PrecisionConstraint"
    return obj


def make_length_constraint(max_length: int):
    obj = SimpleNamespace(max_length=max_length)
    obj._constraint_name = "LengthConstraint"
    return obj


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mapper():
    """A FakerTypeMapper with a fixed seed for reproducibility."""
    return FakerTypeMapper(seed=42)


@pytest.fixture()
def unseeded_mapper():
    return FakerTypeMapper()


# ===========================================================================
# 1. UUID
# ===========================================================================

class TestUUID:
    def test_returns_string(self, mapper):
        val = mapper.generate_for_type_name("uuid")
        assert isinstance(val, str)

    def test_valid_uuid_format(self, mapper):
        val = mapper.generate_for_type_name("uuid")
        parsed = uuid.UUID(val)
        assert str(parsed) == val

    def test_uniqueness(self, mapper):
        values = [mapper.generate_for_type_name("uuid") for _ in range(50)]
        assert len(set(values)) == 50


# ===========================================================================
# 2. Email
# ===========================================================================

class TestEmail:
    def test_returns_string(self, mapper):
        val = mapper.generate_for_type_name("email")
        assert isinstance(val, str)

    def test_contains_at_sign(self, mapper):
        val = mapper.generate_for_type_name("email")
        assert "@" in val

    def test_basic_format(self, mapper):
        val = mapper.generate_for_type_name("email")
        assert re.match(r"[^@]+@[^@]+\.[^@]+", val), f"Unexpected email: {val!r}"


# ===========================================================================
# 3. Name types
# ===========================================================================

class TestNames:
    def test_full_name_is_string(self, mapper):
        assert isinstance(mapper.generate_for_type_name("fullName"), str)

    def test_full_name_has_space(self, mapper):
        val = mapper.generate_for_type_name("fullName")
        assert " " in val

    def test_first_name_is_string(self, mapper):
        assert isinstance(mapper.generate_for_type_name("firstName"), str)

    def test_first_name_non_empty(self, mapper):
        assert mapper.generate_for_type_name("firstName") != ""

    def test_last_name_is_string(self, mapper):
        assert isinstance(mapper.generate_for_type_name("lastName"), str)

    def test_last_name_non_empty(self, mapper):
        assert mapper.generate_for_type_name("lastName") != ""


# ===========================================================================
# 4. Phone
# ===========================================================================

class TestPhone:
    def test_returns_string(self, mapper):
        assert isinstance(mapper.generate_for_type_name("phone"), str)

    def test_non_empty(self, mapper):
        assert mapper.generate_for_type_name("phone") != ""


# ===========================================================================
# 5. Boolean
# ===========================================================================

class TestBoolean:
    def test_returns_bool(self, mapper):
        val = mapper.generate_for_type_name("boolean")
        assert isinstance(val, bool)

    def test_both_values_produced(self):
        """Over many samples both True and False should appear."""
        m = FakerTypeMapper(seed=0)
        values = {m.generate_for_type_name("boolean") for _ in range(30)}
        assert values == {True, False}


# ===========================================================================
# 6. Number
# ===========================================================================

class TestNumber:
    def test_integer_no_range(self, mapper):
        val = mapper.generate_for_type_name("number")
        assert isinstance(val, int)
        assert 0 <= val <= 1000

    def test_integer_with_range(self, mapper):
        rc = make_range_constraint(18, 65)
        val = mapper.generate_for_type_name("number", constraints=[rc])
        assert isinstance(val, int)
        assert 18 <= val <= 65

    def test_float_with_precision(self, mapper):
        rc = make_range_constraint(0.01, 9999.99)
        pc = make_precision_constraint(2)
        val = mapper.generate_for_type_name("number", constraints=[rc, pc])
        assert isinstance(val, float)
        assert 0.01 <= val <= 9999.99
        assert round(val, 2) == val

    def test_boundary_min_max(self):
        m = FakerTypeMapper(seed=1)
        rc = make_range_constraint(5, 5)
        for _ in range(10):
            val = m.generate_for_type_name("number", constraints=[rc])
            assert val == 5

    def test_negative_range(self, mapper):
        rc = make_range_constraint(-100, -1)
        val = mapper.generate_for_type_name("number", constraints=[rc])
        assert -100 <= val <= -1

    def test_zero_precision_returns_int(self, mapper):
        rc = make_range_constraint(1, 100)
        pc = make_precision_constraint(0)
        val = mapper.generate_for_type_name("number", constraints=[rc, pc])
        assert isinstance(val, int)


# ===========================================================================
# 7. Date
# ===========================================================================

class TestDate:
    ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

    def test_returns_string(self, mapper):
        val = mapper.generate_for_type_name("date")
        assert isinstance(val, str)

    def test_iso_format(self, mapper):
        val = mapper.generate_for_type_name("date")
        assert self.ISO_RE.fullmatch(val), f"Not ISO date: {val!r}"

    def test_within_range(self, mapper):
        rc = make_range_constraint("2020-01-01", "2020-12-31")
        val = mapper.generate_for_type_name("date", constraints=[rc])
        d = date.fromisoformat(val)
        assert date(2020, 1, 1) <= d <= date(2020, 12, 31)

    def test_single_day_range(self, mapper):
        rc = make_range_constraint("2023-06-15", "2023-06-15")
        val = mapper.generate_for_type_name("date", constraints=[rc])
        assert val == "2023-06-15"

    def test_date_object_range(self, mapper):
        """Range values can be native date objects from the parser."""
        rc = make_range_constraint(date(2021, 1, 1), date(2021, 12, 31))
        val = mapper.generate_for_type_name("date", constraints=[rc])
        d = date.fromisoformat(val)
        assert date(2021, 1, 1) <= d <= date(2021, 12, 31)

    def test_default_range_reasonable(self, mapper):
        val = mapper.generate_for_type_name("date")
        d = date.fromisoformat(val)
        assert date(2000, 1, 1) <= d <= date(2030, 12, 31)


# ===========================================================================
# 8. Datetime
# ===========================================================================

class TestDatetime:
    ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_returns_string(self, mapper):
        val = mapper.generate_for_type_name("datetime")
        assert isinstance(val, str)

    def test_iso_format(self, mapper):
        val = mapper.generate_for_type_name("datetime")
        assert self.ISO_RE.match(val), f"Not ISO datetime: {val!r}"

    def test_within_range(self, mapper):
        rc = make_range_constraint("2022-01-01", "2022-03-31")
        val = mapper.generate_for_type_name("datetime", constraints=[rc])
        dt = datetime.fromisoformat(val)
        assert datetime(2022, 1, 1) <= dt <= datetime(2022, 3, 31, 23, 59, 59)


# ===========================================================================
# 9. String
# ===========================================================================

class TestString:
    def test_returns_string(self, mapper):
        assert isinstance(mapper.generate_for_type_name("string"), str)

    def test_non_empty(self, mapper):
        assert mapper.generate_for_type_name("string") != ""

    def test_respects_max_length(self, mapper):
        lc = make_length_constraint(20)
        val = mapper.generate_for_type_name("string", constraints=[lc])
        assert len(val) <= 20


# ===========================================================================
# 10. Commerce & Location types
# ===========================================================================

class TestCommerceAndLocation:
    @pytest.mark.parametrize("type_name", [
        "productName",
        "companyName",
        "address",
        "city",
        "country",
        "url",
    ])
    def test_returns_non_empty_string(self, mapper, type_name):
        val = mapper.generate_for_type_name(type_name)
        assert isinstance(val, str)
        assert val != ""

    def test_url_starts_with_http(self, mapper):
        val = mapper.generate_for_type_name("url")
        assert val.startswith("http")


# ===========================================================================
# 11. Enum type
# ===========================================================================

class TestEnum:
    def test_returns_one_of_values(self, mapper):
        enum_type = make_enum_type(["active", "inactive", "banned"])
        val = mapper.generate(enum_type, [])
        assert val in {"active", "inactive", "banned"}

    def test_all_values_reachable(self):
        m = FakerTypeMapper(seed=99)
        enum_type = make_enum_type(["a", "b", "c"])
        seen = set()
        for _ in range(100):
            seen.add(m.generate(enum_type, []))
        assert seen == {"a", "b", "c"}

    def test_single_value_enum(self, mapper):
        enum_type = make_enum_type(["only"])
        assert mapper.generate(enum_type, []) == "only"


# ===========================================================================
# 12. RefType sentinel
# ===========================================================================

class TestRefType:
    def test_returns_sentinel(self, mapper):
        ref_type = make_ref_type("User")
        val = mapper.generate(ref_type, [])
        assert val == "__ref__"


# ===========================================================================
# 13. SimpleType dispatch via generate()
# ===========================================================================

class TestSimpleTypeDispatch:
    def test_email_via_generate(self, mapper):
        ft = make_simple_type("email")
        val = mapper.generate(ft, [])
        assert "@" in val

    def test_uuid_via_generate(self, mapper):
        ft = make_simple_type("uuid")
        val = mapper.generate(ft, [])
        uuid.UUID(val)  # should not raise

    def test_number_via_generate_with_range(self, mapper):
        ft = make_simple_type("number")
        rc = make_range_constraint(1, 10)
        val = mapper.generate(ft, [rc])
        assert 1 <= val <= 10

    def test_unknown_type_falls_back(self, mapper):
        """Unknown type names should not raise; they fall back to a word."""
        ft = make_simple_type("nonExistentType")
        val = mapper.generate(ft, [])
        assert isinstance(val, str)


# ===========================================================================
# 14. Unknown field type class raises ValueError
# ===========================================================================

class TestUnknownTypeClass:
    def test_unknown_class_raises(self, mapper):
        mystery_type = SimpleNamespace(name="mystery")
        # No _type_class_name set, so class name will be "SimpleNamespace"
        with pytest.raises(ValueError, match="Unknown field type class"):
            mapper.generate(mystery_type, [])


# ===========================================================================
# 15. Seed reproducibility
# ===========================================================================

class TestSeedReproducibility:
    def test_same_seed_same_output_number(self):
        m1 = FakerTypeMapper(seed=123)
        m2 = FakerTypeMapper(seed=123)
        rc = make_range_constraint(0, 1_000_000)
        v1 = m1.generate_for_type_name("number", [rc])
        v2 = m2.generate_for_type_name("number", [rc])
        assert v1 == v2

    def test_same_seed_same_output_email(self):
        m1 = FakerTypeMapper(seed=7)
        m2 = FakerTypeMapper(seed=7)
        assert m1.generate_for_type_name("email") == m2.generate_for_type_name("email")

    def test_same_seed_same_output_date(self):
        m1 = FakerTypeMapper(seed=55)
        m2 = FakerTypeMapper(seed=55)
        rc = make_range_constraint("2020-01-01", "2025-12-31")
        assert (
            m1.generate_for_type_name("date", [rc])
            == m2.generate_for_type_name("date", [rc])
        )

    def test_different_seeds_different_output(self):
        """With very high probability two different seeds produce different values."""
        m1 = FakerTypeMapper(seed=1)
        m2 = FakerTypeMapper(seed=2)
        rc = make_range_constraint(0, 10_000_000)
        vals1 = [m1.generate_for_type_name("number", [rc]) for _ in range(20)]
        vals2 = [m2.generate_for_type_name("number", [rc]) for _ in range(20)]
        assert vals1 != vals2

    def test_no_seed_does_not_crash(self, unseeded_mapper):
        val = unseeded_mapper.generate_for_type_name("email")
        assert "@" in val


# ===========================================================================
# 16. Batch generation helpers
# ===========================================================================

class TestBatchGeneration:
    def test_generate_many_count(self, mapper):
        ft = make_simple_type("email")
        vals = mapper.generate_many(ft, [], count=10)
        assert len(vals) == 10

    def test_generate_for_type_name_many_count(self, mapper):
        vals = mapper.generate_for_type_name_many("uuid", count=5)
        assert len(vals) == 5

    def test_generate_many_all_valid(self, mapper):
        ft = make_simple_type("boolean")
        vals = mapper.generate_many(ft, [], count=20)
        assert all(isinstance(v, bool) for v in vals)