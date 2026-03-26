import pytest
from grammar_loader import load_model_from_str
from textx import TextXSemanticError, TextXSyntaxError


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