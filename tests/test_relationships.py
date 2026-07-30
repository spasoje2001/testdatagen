import pytest
from grammar_loader import load_model_from_str
from textx import TextXSemanticError, TextXSyntaxError

def test_relationship_basic_parsing():
    model = load_model_from_str(
        """
        schema Ecommerce {
            entity User {
                fields {
                    id: uuid
                }
            }

            entity Order {
                fields {
                    id: uuid
                }
            }

            relationship Placed {
                from User
                to Order
            }
        }
        """
    )
    # Proveravamo da je parsirano i da se nalazi u elementima šeme
    assert len(model.elements) == 3


def test_relationship_with_properties_and_config():
    model = load_model_from_str(
        """
        schema Ecommerce {
            entity User {
                fields {
                    id: uuid
                }
            }

            entity Order {
                fields {
                    id: uuid
                }
            }

            relationship Placed {
                from User
                to Order

                properties {
                    createdAt: datetime
                    rating: number { range 1..5 }
                }

                config {
                    strategy: one-to-one
                    generate: 100
                    include: [
                        {
                            createdAt: "2020-01-01",
                            rating: 5
                        }
                    ]
                }
            }
        }
        """
    )
    assert model is not None


def test_invalid_relationship_syntax():
    with pytest.raises(TextXSyntaxError):
        load_model_from_str(
            """
            schema Ecommerce {
                entity User { fields { id: uuid } }
                entity Order { fields { id: uuid } }

                relationship Placed {
                    source User
                    to Order
                }
            }
            """
        )