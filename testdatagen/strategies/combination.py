"""
Combination Strategies

Controls how values from different fields within an entity are combined
into complete test records.

This module implements:
  - full: Cartesian product of all field value lists
  - each_used: every value appears at least once, minimal row count

Future additions (separate issues):
  - pairwise: every pair of values from any two fields appears at least once (#14)
"""

import random
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


def each_used_combination(field_values, seed=None):
    """
    Minimal combinations where every value from every field appears at least once.

    Number of rows = max(len(values) for all fields).
    Shorter lists are extended by cycling random picks from their original values,
    then all lists are shuffled so assignments aren't predictable.

    Args:
        field_values: Dict mapping field names to lists of values.
        seed: Random seed for reproducibility (None = non-deterministic).

    Returns:
        List of dicts, e.g. [{"age": 18, "status": "active"}, ...]
    """
    if not field_values:
        return []

    value_lists = list(field_values.values())

    if any(len(vals) == 0 for vals in value_lists):
        return []

    rng = random.Random(seed)

    field_names = list(field_values.keys())
    max_len = max(len(vals) for vals in value_lists)

    # Build extended lists: original values first (guarantees each-used),
    # then fill remaining slots with random picks from original values.
    extended = {}
    for name in field_names:
        original = list(field_values[name])
        padded = list(original)
        while len(padded) < max_len:
            padded.append(rng.choice(original))
        rng.shuffle(padded)
        extended[name] = padded

    return [
        {name: extended[name][i] for name in field_names}
        for i in range(max_len)
    ]


def each_used_combination_count(field_values):
    """
    Calculate the number of rows each-used will produce.

    Simply max(len(values)) across all fields.

    Args:
        field_values: Dict mapping field names to lists of values.

    Returns:
        Int -- number of rows.
    """
    if not field_values:
        return 0

    lengths = [len(vals) for vals in field_values.values()]

    if any(l == 0 for l in lengths):
        return 0

    return max(lengths)