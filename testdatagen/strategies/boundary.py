"""
Boundary Value Analysis (BVA) Strategy

Generates test values at and around boundaries where defects
are most likely to occur.

For a range [min, max]:
  - min-step  (invalid, below range)
  - min       (valid, lower boundary)
  - min+step  (valid, just above min)
  - max-step  (valid, just below max)
  - max       (valid, upper boundary)
  - max+step  (invalid, above range)

Step depends on type:
  - integers: 1
  - decimals: 10^(-precision)
  - dates:    1 day
"""

from datetime import date, datetime, timedelta


def generate_boundary_values(field_type_name, min_val, max_val, precision=0):
    """
    Main entry point for BVA generation.

    Args:
        field_type_name: 'number', 'date', 'datetime'
        min_val: Minimum value of the range
        max_val: Maximum value of the range
        precision: Decimal precision (only for numbers), default 0 (integer)

    Returns:
        List of dicts: [{"value": ..., "category": "valid"|"invalid"}, ...]
    """
    if field_type_name == "number":
        return _number_boundaries(min_val, max_val, precision)
    elif field_type_name == "date":
        return _date_boundaries(min_val, max_val)
    elif field_type_name == "datetime":
        return _datetime_boundaries(min_val, max_val)
    else:
        return []


def generate_count_boundary_values(min_count, max_count):
    """
    BVA for ref[] count constraints (e.g., ref Product[] count 1-10).

    Counts are always integers >= 0.

    Args:
        min_count: Minimum count
        max_count: Maximum count

    Returns:
        List of dicts with boundary values for count.
    """
    return _number_boundaries(min_count, max_count, precision=0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _number_boundaries(min_val, max_val, precision=0):
    """Generate boundary values for numeric ranges."""
    step = 10 ** (-precision) if precision > 0 else 1

    # Round to avoid floating point drift (e.g., 0.01 + 0.01 = 0.020000...004)
    def _round(val):
        return round(val, precision) if precision > 0 else val

    values = []

    # --- Invalid below min ---
    below_min = _round(min_val - step)
    # Skip if min=0, and we're dealing with unsigned-like context (non-negative range)
    # We still generate it but mark invalid -- caller decides if it makes sense
    values.append({"value": below_min, "category": "invalid"})

    # --- Min boundary ---
    values.append({"value": min_val, "category": "valid"})

    # --- Just above min ---
    above_min = _round(min_val + step)
    if above_min <= max_val:
        values.append({"value": above_min, "category": "valid"})

    # --- Just below max ---
    below_max = _round(max_val - step)
    # Avoid duplicate if range is too small (e.g., range 1..2 with step 1)
    if below_max > min_val + step and below_max != above_min:
        values.append({"value": below_max, "category": "valid"})
    elif below_max == min_val + step and below_max not in [v["value"] for v in values]:
        # Edge case: small range where below_max == above_min, already added
        values.append({"value": below_max, "category": "valid"})

    # --- Max boundary ---
    if max_val not in [v["value"] for v in values]:
        values.append({"value": max_val, "category": "valid"})
    else:
        # max_val might equal above_min for tiny ranges -- ensure it's there
        pass

    # --- Invalid above max ---
    above_max = _round(max_val + step)
    values.append({"value": above_max, "category": "invalid"})

    return _deduplicate(values)


def _date_boundaries(min_val, max_val):
    """Generate boundary values for date ranges."""
    min_date = _parse_date(min_val)
    max_date = _parse_date(max_val)
    one_day = timedelta(days=1)

    values = [
        {"value": (min_date - one_day).isoformat(), "category": "invalid"},
        {"value": min_date.isoformat(), "category": "valid"},
        {"value": (min_date + one_day).isoformat(), "category": "valid"},
        {"value": (max_date - one_day).isoformat(), "category": "valid"},
        {"value": max_date.isoformat(), "category": "valid"},
        {"value": (max_date + one_day).isoformat(), "category": "invalid"},
    ]

    return _deduplicate(values)


def _datetime_boundaries(min_val, max_val):
    """Generate boundary values for datetime ranges."""
    min_dt = _parse_datetime(min_val)
    max_dt = _parse_datetime(max_val)
    one_day = timedelta(days=1)

    values = [
        {"value": (min_dt - one_day).isoformat(), "category": "invalid"},
        {"value": min_dt.isoformat(), "category": "valid"},
        {"value": (min_dt + one_day).isoformat(), "category": "valid"},
        {"value": (max_dt - one_day).isoformat(), "category": "valid"},
        {"value": max_dt.isoformat(), "category": "valid"},
        {"value": (max_dt + one_day).isoformat(), "category": "invalid"},
    ]

    return _deduplicate(values)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _parse_date(val):
    """Parse a date value -- handles str, date, and datetime objects."""
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val)
    raise ValueError(f"Cannot parse date from: {val} (type: {type(val)})")


def _parse_datetime(val):
    """Parse a datetime value."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    raise ValueError(f"Cannot parse datetime from: {val} (type: {type(val)})")


def _deduplicate(values):
    """Remove duplicate values, keeping the first occurrence."""
    seen = set()
    result = []
    for item in values:
        if item["value"] not in seen:
            seen.add(item["value"])
            result.append(item)
    return result