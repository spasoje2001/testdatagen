import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from textx import TextXSyntaxError
from grammar_loader import get_metamodel, load_model_from_str


def test_parse_minimal_schema():
    model = load_model_from_str(
        """
        schema Minimal {
            entity User {
                fields {
                    id: int
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
    assert model.entities[0].fields[0].type == "int"


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
                    id: int
                    email: string
                }
            }

            entity Product {
                fields {
                    sku: string
                    price: decimal
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

    assert model.name == "ExampleSchema"
    assert len(model.entities) == 1


def test_invalid_syntax_raises_error():
    with pytest.raises(TextXSyntaxError):
        load_model_from_str(
            """
            schema Broken {
                entity User {
                    fields {
                        id int
                    }
                }
            }
            """
        )
