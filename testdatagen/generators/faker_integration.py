"""
Faker Integration Module for TestDataGen (#8)

Maps DSL field types to Faker providers and custom generators.
Handles seed-based reproducibility, range constraints, enum, boolean, and ref types.
"""

import random
import uuid
from datetime import date, datetime, timedelta
from typing import Any, List, Optional

from faker import Faker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_constraint(constraints, class_name):
    """Return the first constraint whose class name matches, or None."""
    if not constraints:
        return None
    for c in constraints:
        name = getattr(c, "_constraint_name", None) or c.__class__.__name__
        if name == class_name:
            return c
    return None


def _parse_date(value) -> date:
    """
    Accept a date object, datetime object, or ISO-format string and return a date.
    textX parses date ranges as strings ('2020-01-01') or native date objects depending
    on grammar configuration, so we handle both.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value.strip('"').strip("'"))
    raise TypeError(f"Cannot convert {type(value)} to date: {value!r}")


def _date_to_str(d: date) -> str:
    return d.isoformat()


def _datetime_to_str(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------------
# FakerTypeMapper
# ---------------------------------------------------------------------------

class FakerTypeMapper:
    """
    Maps DSL field types to generated values.

    Usage
    -----
    mapper = FakerTypeMapper(seed=12345)
    value  = mapper.generate(field.type, field.constraints)
    """

    def __init__(self, seed: Optional[int] = None):
        self._seed = seed
        self._random = random.Random(seed)   # per-instance Random, never touches global
        if seed is not None:
            Faker.seed(seed)                 # seed Faker's class-level generator first
        self.faker = Faker()                 # then create the instance so it inherits the seed
        if seed is not None:
            self.faker.seed_instance(seed)   # isolate this instance from others

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, field_type, constraints=None) -> Any:
        """
        Generate a single value for *field_type* respecting *constraints*.

        Parameters
        ----------
        field_type  : textX model object  (SimpleType, EnumType, RefType, ...)
        constraints : list of textX constraint objects, or None

        Returns
        -------
        A Python scalar (str, int, float, bool, None, date-string, ...).
        For RefType the caller is responsible for resolving the actual
        foreign-key value; this method returns a sentinel ``"__ref__"``.
        """
        # Support both real textX objects and SimpleNamespace mocks via _type_class_name
        class_name = getattr(field_type, "_type_class_name", None) or field_type.__class__.__name__

        dispatch = {
            "SimpleType": self._generate_simple,
            "EnumType":   self._generate_enum,
            "RefType":    self._generate_ref,
        }

        handler = dispatch.get(class_name)
        if handler is None:
            raise ValueError(f"Unknown field type class: {class_name!r}")

        return handler(field_type, constraints or [])

    def generate_for_type_name(self, type_name: str, constraints=None) -> Any:
        """
        Convenience method: generate a value given just the type *name* string
        (e.g. ``"number"``, ``"email"``).  Used by tests and by generators
        that have already resolved the type name.
        """
        return self._dispatch_simple_name(type_name, constraints or [])

    # ------------------------------------------------------------------
    # Dispatch helpers
    # ------------------------------------------------------------------

    def _generate_simple(self, field_type, constraints: list) -> Any:
        type_name = getattr(field_type, "name", "string")
        return self._dispatch_simple_name(type_name, constraints)

    def _dispatch_simple_name(self, type_name: str, constraints: list) -> Any:
        handlers = {
            # --- identity / ID types ---
            "uuid":        self._gen_uuid,
            # --- personal info ---
            "email":       self._gen_email,
            "fullName":    self._gen_full_name,
            "firstName":   self._gen_first_name,
            "lastName":    self._gen_last_name,
            "phone":       self._gen_phone,
            # --- numeric ---
            "number":      self._gen_number,
            "boolean":     self._gen_boolean,
            # --- temporal ---
            "date":        self._gen_date,
            "datetime":    self._gen_datetime,
            # --- text / string ---
            "string":      self._gen_string,
            # --- commerce / location ---
            "productName": self._gen_product_name,
            "companyName": self._gen_company_name,
            "address":     self._gen_address,
            "city":        self._gen_city,
            "country":     self._gen_country,
            "url":         self._gen_url,
        }
        handler = handlers.get(type_name)
        if handler is None:
            # Graceful fallback: return a random word so unknown types don't crash
            return self.faker.word()
        return handler(constraints)

    def _generate_enum(self, field_type, constraints: list) -> str:
        values: List[str] = field_type.values  # list of strings from grammar
        return self._random.choice(values)      # use per-instance random, not global

    def _generate_ref(self, field_type, constraints: list) -> str:
        # The SQL/JSON generators will replace this sentinel with a real FK.
        return "__ref__"

    # ------------------------------------------------------------------
    # Individual type generators
    # NOTE: Always use self._random, never the global random module.
    # ------------------------------------------------------------------

    # --- UUID ---

    def _gen_uuid(self, constraints: list) -> str:
        # Generate a deterministic UUID from the seeded random state
        rand_int = self._random.getrandbits(128)
        # Set version 4 bits and variant bits per RFC 4122
        rand_int &= ~(0xc000 << 48)
        rand_int |=  (0x8000 << 48)
        rand_int &= ~(0xf000 << 64)
        rand_int |=  (0x4000 << 64)
        return str(uuid.UUID(int=rand_int))

    # --- Personal ---

    def _gen_email(self, constraints: list) -> str:
        return self.faker.email()

    def _gen_full_name(self, constraints: list) -> str:
        return self.faker.name()

    def _gen_first_name(self, constraints: list) -> str:
        return self.faker.first_name()

    def _gen_last_name(self, constraints: list) -> str:
        return self.faker.last_name()

    def _gen_phone(self, constraints: list) -> str:
        return self.faker.phone_number()

    # --- Numeric ---

    def _gen_number(self, constraints: list) -> Any:
        """
        Generate a number respecting RangeConstraint and PrecisionConstraint.
        Falls back to a random integer in [0, 1000] when no range is given.
        """
        range_c     = _get_constraint(constraints, "RangeConstraint")
        precision_c = _get_constraint(constraints, "PrecisionConstraint")
        precision: int = getattr(precision_c, "value", 0) if precision_c else 0

        if range_c is not None:
            min_val = float(range_c.min)
            max_val = float(range_c.max)
        else:
            min_val, max_val = 0.0, 1000.0

        if precision == 0:
            return self._random.randint(int(min_val), int(max_val))
        else:
            value = self._random.uniform(min_val, max_val)
            return round(value, precision)

    def _gen_boolean(self, constraints: list) -> bool:
        return self._random.choice([True, False])

    # --- Temporal ---

    def _gen_date(self, constraints: list) -> str:
        """Return an ISO date string (YYYY-MM-DD)."""
        range_c = _get_constraint(constraints, "RangeConstraint")
        if range_c is not None:
            start = _parse_date(range_c.min)
            end   = _parse_date(range_c.max)
        else:
            start = date(2000, 1, 1)
            end   = date(2030, 12, 31)

        delta_days = (end - start).days
        if delta_days < 0:
            raise ValueError(f"Date range start {start} is after end {end}")
        offset = self._random.randint(0, delta_days)
        return _date_to_str(start + timedelta(days=offset))

    def _gen_datetime(self, constraints: list) -> str:
        """Return an ISO datetime string."""
        range_c = _get_constraint(constraints, "RangeConstraint")
        if range_c is not None:
            start_date = _parse_date(range_c.min)
            end_date   = _parse_date(range_c.max)
            start = datetime(start_date.year, start_date.month, start_date.day)
            end   = datetime(end_date.year,   end_date.month,   end_date.day, 23, 59, 59)
        else:
            start = datetime(2000, 1, 1)
            end   = datetime(2030, 12, 31, 23, 59, 59)

        delta_secs = int((end - start).total_seconds())
        if delta_secs < 0:
            raise ValueError("Datetime range start is after end")
        offset = self._random.randint(0, delta_secs)
        return _datetime_to_str(start + timedelta(seconds=offset))

    # --- Text ---

    def _gen_string(self, constraints: list) -> str:
        """
        Generate a string. Honours an optional LengthConstraint
        (``max_length`` attribute) when present.
        """
        length_c = _get_constraint(constraints, "LengthConstraint")
        max_len: Optional[int] = getattr(length_c, "max_length", None) if length_c else None
        limit = max_len or 200
        text = self.faker.text(max_nb_chars=limit)
        # Faker doesn't always guarantee the limit, so hard-truncate
        return text[:limit]

    # --- Commerce / Location ---

    def _gen_product_name(self, constraints: list) -> str:
        # Faker has no dedicated product-name provider; catch_phrase gives
        # realistic-sounding multi-word names used for products.
        return self.faker.catch_phrase()

    def _gen_company_name(self, constraints: list) -> str:
        return self.faker.company()

    def _gen_address(self, constraints: list) -> str:
        return self.faker.address().replace("\n", ", ")

    def _gen_city(self, constraints: list) -> str:
        return self.faker.city()

    def _gen_country(self, constraints: list) -> str:
        return self.faker.country()

    def _gen_url(self, constraints: list) -> str:
        return self.faker.url()

    # ------------------------------------------------------------------
    # Batch generation
    # ------------------------------------------------------------------

    def generate_many(self, field_type, constraints=None, count: int = 1) -> List[Any]:
        """Generate *count* values for a field type."""
        return [self.generate(field_type, constraints) for _ in range(count)]

    def generate_for_type_name_many(
        self,
        type_name: str,
        constraints=None,
        count: int = 1,
    ) -> List[Any]:
        """Convenience batch variant of generate_for_type_name."""
        return [self.generate_for_type_name(type_name, constraints) for _ in range(count)]