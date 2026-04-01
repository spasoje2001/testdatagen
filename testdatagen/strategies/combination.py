"""
Combination Strategies

Controls how values from different fields within an entity are combined
into complete test records.

This module implements:
  - full: Cartesian product of all field value lists

Future additions (separate issues):
  - each_used: every value appears at least once (#13)
  - pairwise: every pair of values from any two fields appears at least once (#14)
"""

from itertools import product


def full_combination(field_values, limit=None):
    """
    Full Cartesian product of all field value lists.

    Generates every possible combination of field values. Use for small
    entities or when exhaustive coverage is required.

    Args:
        field_values: Dict mapping field names to lists of values.
                      e.g. {"age": [18, 65], "status": ["active", "inactive"]}
        limit: Maximum number of combinations to generate (None = all).
               Maps to the `generate` config option.

    Yields:
        Dict per combination, e.g. {"age": 18, "status": "active"}
    """
    if not field_values:
        return

    field_names = list(field_values.keys())
    value_lists = [field_values[name] for name in field_names]

    # Skip if any field has no values
    if any(len(vals) == 0 for vals in value_lists):
        return

    count = 0
    for combo in product(*value_lists):
        if limit is not None and count >= limit:
            return
        yield dict(zip(field_names, combo))
        count += 1


def full_combination_count(field_values):
    """
    Calculate total number of combinations without generating them.

    Useful for coverage reporting: compare generated vs total possible.

    Args:
        field_values: Dict mapping field names to lists of values.

    Returns:
        Int -- total Cartesian product size.
    """
    if not field_values:
        return 0

    total = 1
    for vals in field_values.values():
        if len(vals) == 0:
            return 0
        total *= len(vals)
    return total