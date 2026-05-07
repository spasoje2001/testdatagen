"""
Combination Strategies

Controls how values from different fields within an entity are combined
into complete test records.

This module implements:
  - full: Cartesian product of all field value lists
  - each_used: every value appears at least once, minimal row count
  - pairwise: every pair of values from any two fields appears at least once
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


def pairwise_combination(field_values, seed=None):
    """
    Generate combinations where every pair of values from any two fields
    appears at least once, using a greedy All-Pairs algorithm.

    For each new row, pick the combination of values that covers the most
    uncovered pairs. This minimizes the total number of rows while
    guaranteeing full pairwise coverage.

    Important: for 2 fields, pairwise = full Cartesian (no reduction).
    Meaningful reduction only occurs with 3+ fields.

    Args:
        field_values: Dict mapping field names to lists of values.
        seed: Random seed for reproducibility (None = non-deterministic).
              Used to break ties when multiple candidates cover equal pairs.

    Returns:
        List of dicts, e.g. [{"age": 18, "status": "active"}, ...]
    """
    if not field_values:
        return []

    value_lists = list(field_values.values())

    if any(len(vals) == 0 for vals in value_lists):
        return []

    field_names = list(field_values.keys())
    n_fields = len(field_names)

    # Single field -- just return each value
    if n_fields == 1:
        return [{field_names[0]: v} for v in field_values[field_names[0]]]

    rng = random.Random(seed)

    # Build set of all pairs that need covering.
    # A pair is (field_index_i, field_index_j, value_i, value_j).
    uncovered = set()
    for i in range(n_fields):
        for j in range(i + 1, n_fields):
            for vi in field_values[field_names[i]]:
                for vj in field_values[field_names[j]]:
                    uncovered.add((i, j, vi, vj))

    combinations = []

    while uncovered:
        best_combo = _find_best_row(field_names, field_values, uncovered, rng)
        combinations.append(best_combo)

        # Remove all pairs covered by this row
        for i in range(n_fields):
            for j in range(i + 1, n_fields):
                pair = (i, j, best_combo[field_names[i]], best_combo[field_names[j]])
                uncovered.discard(pair)

    return combinations


def pairwise_coverage(field_values, combinations):
    """
    Calculate pairwise coverage statistics for a set of combinations.

    Useful for coverage reporting.

    Args:
        field_values: Dict mapping field names to lists of values.
        combinations: List of combination dicts (as produced by pairwise_combination).

    Returns:
        Dict with:
          - total_pairs: total number of unique pairs to cover
          - covered_pairs: number of pairs actually covered
          - coverage: ratio (0.0 to 1.0)
          - uncovered: set of (field_i, field_j, val_i, val_j) still uncovered
    """
    field_names = list(field_values.keys())
    n_fields = len(field_names)

    all_pairs = set()
    for i in range(n_fields):
        for j in range(i + 1, n_fields):
            for vi in field_values[field_names[i]]:
                for vj in field_values[field_names[j]]:
                    all_pairs.add((i, j, vi, vj))

    covered = set()
    for combo in combinations:
        for i in range(n_fields):
            for j in range(i + 1, n_fields):
                pair = (i, j, combo[field_names[i]], combo[field_names[j]])
                if pair in all_pairs:
                    covered.add(pair)

    total = len(all_pairs)
    return {
        "total_pairs": total,
        "covered_pairs": len(covered),
        "coverage": len(covered) / total if total > 0 else 1.0,
        "uncovered": all_pairs - covered,
    }


# ---------------------------------------------------------------------------
# Internal helpers for pairwise
# ---------------------------------------------------------------------------

def _pairs_covered_by_row(row, field_names, uncovered):
    """Count how many uncovered pairs a candidate row would cover."""
    n_fields = len(field_names)
    count = 0
    for i in range(n_fields):
        for j in range(i + 1, n_fields):
            pair = (i, j, row[field_names[i]], row[field_names[j]])
            if pair in uncovered:
                count += 1
    return count


def _find_best_row(field_names, field_values, uncovered, rng):
    """
    Greedy search: find the row that covers the most uncovered pairs.

    Strategy: pick an uncovered pair, then try all possible values for
    the remaining fields, scoring each candidate by how many additional
    uncovered pairs it covers. This avoids iterating over the entire
    Cartesian product (which would defeat the purpose for large inputs).
    """
    n_fields = len(field_names)

    # Pick an arbitrary uncovered pair to anchor the search
    anchor = next(iter(uncovered))
    anchor_i, anchor_j, anchor_vi, anchor_vj = anchor

    # Build candidate rows by fixing the anchor pair and trying all
    # combinations of the remaining fields
    other_indices = [k for k in range(n_fields) if k != anchor_i and k != anchor_j]

    best_row = None
    best_score = -1

    if not other_indices:
        # Only 2 fields -- the anchor pair fully determines the row
        row = {}
        row[field_names[anchor_i]] = anchor_vi
        row[field_names[anchor_j]] = anchor_vj
        return row

    # For remaining fields, try all value combinations
    other_value_lists = [field_values[field_names[k]] for k in other_indices]

    candidates = list(product(*other_value_lists))
    # Shuffle to break ties randomly for reproducibility
    rng.shuffle(candidates)

    for other_vals in candidates:
        row = {}
        row[field_names[anchor_i]] = anchor_vi
        row[field_names[anchor_j]] = anchor_vj
        for idx, k in enumerate(other_indices):
            row[field_names[k]] = other_vals[idx]

        score = _pairs_covered_by_row(row, field_names, uncovered)
        if score > best_score:
            best_score = score
            best_row = row

    return best_row