import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from textx import TextXSyntaxError, TextXSemanticError
from grammar_loader import get_metamodel, load_model_from_str


def test_parse_minimal_schema():
    model = load_model_from_str(
        """
        schema Minimal {
            entity User {
                fields {
                    id: uuid
                }
            }
        }
        """
    )

    assert model.name == "Minimal"
    assert len(model.entities) == 1
    assert model.entities[0].name == "User"
    assert len(model.entities[0].fields) == 1
    assert model.entities[0].fields[0].name == "id"
    assert model.entities[0].fields[0].type.name == "uuid"


def test_parse_schema_with_multiple_entities():
    model = load_model_from_str(
        """
        schema Complex {
            description: "Multi entity schema"
            seed: 7
            strategy: smart
            combination_strategy: full

            entity User {
                fields {
                    id: uuid 
                    email: email
                }
            }

            entity Product {
                fields {
                    sku: string
                    price: number { range 1..100000, boundary }
                }
                config {
                    region: EU
                    enabled: true
                }
            }
        }
        """
    )

    assert model.description == "Multi entity schema"
    assert model.seed == 7
    assert model.strategy == "smart"
    assert model.combination_strategy == "full"
    assert [entity.name for entity in model.entities] == ["User", "Product"]
    assert [field.name for field in model.entities[1].fields] == ["sku", "price"]
    assert model.entities[1].config is not None
    assert len(model.entities[1].config.entries) == 2


def test_parse_example_schema_file_without_errors():
    metamodel = get_metamodel()
    model = metamodel.model_from_file(str(PROJECT_ROOT / "examples" / "example.tdg"))

    assert model.name == "TestData"
    assert len(model.entities) == 1


def test_invalid_syntax_raises_error():
    with pytest.raises(TextXSyntaxError):
        load_model_from_str(
            """
            schema Broken {
                entity User {
                    fields {
                        id uuid
                    }
                }
            }
            """
        )

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


@pytest.mark.parametrize(
    "field_type",
    [
        "uuid",
        "email",
        "fullName",
        "firstName",
        "lastName",
        "number",
        "boolean",
        "date",
        "datetime",
        "string",
        "productName",
        "companyName",
        "address",
        "city",
        "country",
        "phone",
        "url",
    ],
)
def test_all_simple_field_types_parse(field_type):
    model = load_model_from_str(wrap_field(f"value: {field_type}"))
    field = model.entities[0].fields[0]
    assert field.name == "value"


def test_enum_field_type_parses():
    model = load_model_from_str(
        wrap_field('status: enum["NEW", "ACTIVE", "BLOCKED"]')
    )
    field = model.entities[0].fields[0]
    assert field.type.__class__.__name__ == "EnumType"
    assert field.type.values == ["NEW", "ACTIVE", "BLOCKED"]


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
