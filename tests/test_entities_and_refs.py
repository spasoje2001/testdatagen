import pytest
from grammar_loader import load_model_from_str
from validation import InvalidGenerateCountError, InvalidRangeError


def test_entity_config_generate_and_combination_strategy():
    model = load_model_from_str(
        """
        schema Demo {
            entity User {
                fields {
                    id: uuid
                    age: number
                }
                config {
                    generate: 100
                    combination_strategy: pairwise
                }
            }
        }
        """
    )

    entity = model.entities[0]
    assert entity.config is not None
    assert len(entity.config.options) == 2

    generate_option = next(
        option for option in entity.config.options
        if option.__class__.__name__ == "GenerateOption"
    )
    strategy_option = next(
        option for option in entity.config.options
        if option.__class__.__name__ == "EntityCombinationStrategyOption"
    )

    assert generate_option.generate == 100
    assert strategy_option.combination_strategy == "pairwise"

def test_simple_ref_type():
    model = load_model_from_str(
        """
        schema Demo {
            entity User {
                fields {
                    id: uuid
                }
            }

            entity Order {
                fields {
                    owner: ref User
                }
            }
        }
        """
    )

    field = model.entities[1].fields[0]
    assert field.name == "owner"
    assert field.type.__class__.__name__ == "RefType"
    assert field.type.entity.name == "User"
    assert field.type.array is False

def test_array_ref_with_count():
    model = load_model_from_str(
        """
        schema Demo {
            entity User {
                fields {
                    id: uuid
                }
            }

            entity Team {
                fields {
                    members: ref User[] count 1..10
                }
            }
        }
        """
    )

    field = model.entities[1].fields[0]
    assert field.type.__class__.__name__ == "RefType"
    assert field.type.entity.name == "User"
    assert field.type.array is True
    assert field.type.min == 1
    assert field.type.max == 10

def test_generate_must_be_positive():
    with pytest.raises(InvalidGenerateCountError) as exc:
        load_model_from_str(
            """
            schema Demo {
                entity User {
                    fields {
                        id: uuid
                    }
                    config {
                        generate: 0
                    }
                }
            }
            """
        )

    assert "generate must be a positive integer" in str(exc.value)

def test_invalid_number_range_raises_error():
    with pytest.raises(InvalidRangeError) as exc:
        load_model_from_str(
            """
            schema Demo {
                entity User {
                    fields {
                        age: number { range 10..10 }
                    }
                }
            }
            """
        )

    assert "min must be less than max" in str(exc.value)