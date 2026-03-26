import pytest
from grammar_loader import load_model_from_str
from textx import TextXSemanticError, TextXSyntaxError
from validation import InvalidGenerateCountError, InvalidRangeError

def wrap_field(field_definition: str) -> str:
    return f"""
    schema Demo {{
        entity User {{
            fields {{
                {field_definition}
            }}
        }}
    }}
    """

def test_number_range_constraint():
    model = load_model_from_str(
        wrap_field("age: number { range 18..65 }")
    )
    field = model.entities[0].fields[0]
    assert field.constraints[0].__class__.__name__ == "RangeConstraint"


def test_date_range_constraint():
    model = load_model_from_str(
        wrap_field('birth_date: date { range "2000-01-01".."2020-12-31" }')
    )
    field = model.entities[0].fields[0]
    assert field.constraints[0].min == "2000-01-01"
    assert field.constraints[0].max == "2020-12-31"


def test_boundary_constraint():
    model = load_model_from_str(
        wrap_field("score: number { boundary }")
    )
    assert model.entities[0].fields[0].constraints[0].__class__.__name__ == "BoundaryConstraint"


def test_partition_constraint():
    model = load_model_from_str(
        wrap_field("score: number { partition 5 }")
    )
    assert model.entities[0].fields[0].constraints[0].value == 5


def test_partitions_constraint():
    model = load_model_from_str(
        wrap_field("score: number { partitions[10, 20, 30] }")
    )
    assert model.entities[0].fields[0].constraints[0].values == [10, 20, 30]


def test_unique_constraint():
    model = load_model_from_str(
        wrap_field("id: uuid { unique }")
    )
    assert model.entities[0].fields[0].constraints[0].__class__.__name__ == "UniqueConstraint"


def test_precision_constraint():
    model = load_model_from_str(
        wrap_field("price: number { precision 2 }")
    )
    assert model.entities[0].fields[0].constraints[0].value == 2


def test_special_constraint():
    model = load_model_from_str(
        wrap_field('code: string { special["N/A", "UNKNOWN"] }')
    )
    assert model.entities[0].fields[0].constraints[0].values == ["N/A", "UNKNOWN"]


def test_coverage_constraint():
    model = load_model_from_str(
        wrap_field("age: number { coverage 80 }")
    )
    assert model.entities[0].fields[0].constraints[0].value == 80


def test_include_constraint():
    model = load_model_from_str(
        wrap_field("email: email { include[null, empty, invalid] }")
    )
    assert model.entities[0].fields[0].constraints[0].values == ["null", "empty", "invalid"]


def test_field_level_strategy_override():
    model = load_model_from_str(
        wrap_field("age: number { strategy boundary }")
    )
    assert model.entities[0].fields[0].constraints[0].value == "boundary"


def test_combined_constraints_on_single_field():
    model = load_model_from_str(
        wrap_field(
            'age: number { range 18..65, boundary, partition 5, precision 0, '
            'special["17", "66"], coverage 100, include[invalid], strategy smart }'
        )
    )
    field = model.entities[0].fields[0]
    assert len(field.constraints) == 8


def test_invalid_range_on_string_field():
    with pytest.raises(TextXSemanticError):
        load_model_from_str(
            wrap_field('name: string { range "A".."Z" }')
        )


def test_invalid_precision_on_boolean_field():
    with pytest.raises(TextXSemanticError):
        load_model_from_str(
            wrap_field("flag: boolean { precision 2 }")
        )


def test_invalid_partition_and_partitions_together():
    with pytest.raises(TextXSemanticError):
        load_model_from_str(
            wrap_field("age: number { partition 5, partitions[10, 20] }")
        )


def test_invalid_coverage_out_of_bounds():
    with pytest.raises(TextXSemanticError):
        load_model_from_str(
            wrap_field("age: number { coverage 120 }")
        )


def test_invalid_duplicate_include_values():
    with pytest.raises(TextXSemanticError):
        load_model_from_str(
            wrap_field("name: string { include[null, null] }")
        )


def test_invalid_syntax_for_constraint_block():
    with pytest.raises(TextXSyntaxError):
        load_model_from_str(
            wrap_field("age: number { range 1..10 boundary }")
        )
