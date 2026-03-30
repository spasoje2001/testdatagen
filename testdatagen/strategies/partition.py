"""
Equivalence Partitioning (EP) Strategy

Divides input ranges into equivalence classes and generates one
representative value from the middle of each partition.

For a range [min, max] with N partitions:
  - Partition 1: [min, min + step)           -> midpoint
  - Partition 2: [min + step, min + 2*step)  -> midpoint
  - ...
  - Partition N: [..., max]                  -> midpoint

Where step = (max - min) / N

For enums, each value is its own partition -- returns all values.
"""

from datetime import date, datetime, timedelta
import math


def generate_partition_values(field_type_name, min_val, max_val,
                              num_partitions=3, precision=0):
    """
    Main entry point for EP generation.

    Args:
        field_type_name: 'number', 'date', 'datetime'
        min_val: Minimum value of the range
        max_val: Maximum value of the range
        num_partitions: Number of partitions to divide range into (default 3)
        precision: Decimal precision (only for numbers), default 0

    Returns:
        List of dicts: [{"value": ..., "partition": (start, end)}, ...]
    """
    if num_partitions < 1:
        num_partitions = 1

    if field_type_name == "number":
        return _number_partitions(min_val, max_val, num_partitions, precision)
    elif field_type_name == "date":
        return _date_partitions(min_val, max_val, num_partitions)
    elif field_type_name == "datetime":
        return _datetime_partitions(min_val, max_val, num_partitions)
    else:
        return []


def generate_enum_partition_values(enum_values):
    """
    EP for enum types -- each value is its own partition.

    Args:
        enum_values: List of enum string values, e.g. ["active", "inactive", "banned"]

    Returns:
        List of dicts with each enum value as a representative.
    """
    return [
        {"value": val, "partition": (val, val)}
        for val in enum_values
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _number_partitions(min_val, max_val, num_partitions, precision=0):
    """Generate representative values for numeric range partitions."""
    if min_val == max_val:
        return [{"value": min_val, "partition": (min_val, max_val)}]

    step = (max_val - min_val) / num_partitions
    values = []

    for i in range(num_partitions):
        p_min = min_val + (i * step)
        p_max = min_val + ((i + 1) * step)
        midpoint = (p_min + p_max) / 2

        if precision > 0:
            midpoint = round(midpoint, precision)
            p_min = round(p_min, precision)
            p_max = round(p_max, precision)
        else:
            # For integers, round midpoint to nearest int
            midpoint = round(midpoint)
            p_min = round(p_min)
            p_max = round(p_max)

        values.append({
            "value": midpoint,
            "partition": (p_min, p_max),
        })

    return values


def _date_partitions(min_val, max_val, num_partitions):
    """Generate representative values for date range partitions."""
    min_date = _parse_date(min_val)
    max_date = _parse_date(max_val)
    total_days = (max_date - min_date).days

    if total_days == 0:
        return [{"value": min_date.isoformat(), "partition": (min_date.isoformat(), max_date.isoformat())}]

    step_days = total_days / num_partitions
    values = []

    for i in range(num_partitions):
        p_min = min_date + timedelta(days=math.floor(i * step_days))
        p_max = min_date + timedelta(days=math.floor((i + 1) * step_days))
        mid_days = math.floor(i * step_days + step_days / 2)
        midpoint = min_date + timedelta(days=mid_days)

        values.append({
            "value": midpoint.isoformat(),
            "partition": (p_min.isoformat(), p_max.isoformat()),
        })

    return values


def _datetime_partitions(min_val, max_val, num_partitions):
    """Generate representative values for datetime range partitions."""
    min_dt = _parse_datetime(min_val)
    max_dt = _parse_datetime(max_val)
    total_seconds = (max_dt - min_dt).total_seconds()

    if total_seconds == 0:
        return [{"value": min_dt.isoformat(), "partition": (min_dt.isoformat(), max_dt.isoformat())}]

    step_seconds = total_seconds / num_partitions
    values = []

    for i in range(num_partitions):
        p_min = min_dt + timedelta(seconds=i * step_seconds)
        p_max = min_dt + timedelta(seconds=(i + 1) * step_seconds)
        midpoint = min_dt + timedelta(seconds=i * step_seconds + step_seconds / 2)

        values.append({
            "value": midpoint.isoformat(),
            "partition": (p_min.isoformat(), p_max.isoformat()),
        })

    return values


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