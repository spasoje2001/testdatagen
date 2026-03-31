"""
Edge Case Generation Strategy

Generates special test values based on field constraints:
  - null    (None)
  - empty   ("")
  - invalid (type-specific malformed values)
  - special (custom user-defined edge values)
  - coverage: all for enums (ensure every value appears)

These values are driven by the `include` and `special` constraints
in the .tdg schema.
"""


# ---------------------------------------------------------------------------
# Invalid value lookup per field type
# ---------------------------------------------------------------------------

INVALID_VALUES = {
    "email": "invalid-email-format",
    "url": "not-a-valid-url",
    "uuid": "not-a-uuid",
    "phone": "123",
    "date": "not-a-date",
    "datetime": "not-a-datetime",
    "number": "NaN",
    "boolean": "not-a-bool",
    "string": None,        # No meaningful "invalid" for free-text
    "fullName": "",
    "firstName": "",
    "lastName": "",
    "address": "",
    "city": "",
    "country": "",
    "companyName": "",
    "productName": "",
}


def generate_edge_cases(field_type_name, include_values=None, special_values=None):
    """
    Generate edge case values based on include and special constraints.

    Args:
        field_type_name: 'email', 'url', 'uuid', 'number', etc.
        include_values: List of strings from include constraint,
                        e.g. ["null", "empty", "invalid"]
        special_values: List of custom values from special constraint,
                        e.g. [0, 1, 999, 1000]

    Returns:
        List of dicts: [{"value": ..., "edge_type": "null"|"empty"|"invalid"|"special"}, ...]
    """
    include_values = include_values or []
    special_values = special_values or []
    cases = []

    # --- null ---
    if "null" in include_values:
        cases.append({"value": None, "edge_type": "null"})

    # --- empty ---
    if "empty" in include_values:
        cases.append({"value": "", "edge_type": "empty"})

    # --- invalid ---
    if "invalid" in include_values:
        invalid_val = INVALID_VALUES.get(field_type_name, "INVALID")
        cases.append({"value": invalid_val, "edge_type": "invalid"})

    # --- special (user-defined) ---
    for val in special_values:
        cases.append({"value": val, "edge_type": "special"})

    return cases


def generate_enum_coverage(enum_values):
    """
    For enums with coverage: all, ensure every value is represented.

    This is distinct from EP's generate_enum_partition_values -- that one
    is about partitioning strategy, this one explicitly fulfills the
    'coverage: all' constraint.

    Args:
        enum_values: List of enum string values, e.g. ["active", "inactive", "banned"]

    Returns:
        List of dicts with each enum value marked as a coverage case.
    """
    return [
        {"value": val, "edge_type": "enum_coverage"}
        for val in enum_values
    ]