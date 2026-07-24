"""
Unit tests for testdatagen/generators/neo4j_generator.py

Run with:
    pytest tests/test_neo4j_generator.py -v
"""

import re
import pytest

from testdatagen.generators.neo4j_generator import Neo4JGenerator, format_value_neo4j
from grammar_loader import load_model_from_str


# ===========================================================================
# 1. format_value_neo4j — type conversion & escaping
# ===========================================================================

class TestFormatValueCypher:
    def test_none_becomes_null(self):
        assert format_value_neo4j(None) == "null"

    def test_true_becomes_boolean(self):
        assert format_value_neo4j(True) == "true"

    def test_false_becomes_boolean(self):
        assert format_value_neo4j(False) == "false"

    def test_integer_stays_number(self):
        assert format_value_neo4j(42) == "42"

    def test_float_stays_number(self):
        assert format_value_neo4j(3.14) == "3.14"

    def test_zero_stays_number(self):
        assert format_value_neo4j(0) == "0"

    def test_negative_number(self):
        assert format_value_neo4j(-7) == "-7"

    def test_string_is_quoted(self):
        assert format_value_neo4j("hello") == '"hello"'

    def test_empty_string_is_quoted(self):
        assert format_value_neo4j("") == '""'

    def test_string_with_special_chars_escaped(self):
        val = format_value_neo4j("it's a \"test\"")
        assert '"' in val
        assert "test" in val

    def test_date_becomes_iso_string_quoted(self):
        from datetime import date
        val = format_value_neo4j(date(2024, 6, 15))
        assert val == '"2024-06-15"'

    def test_datetime_becomes_iso_string_quoted(self):
        from datetime import datetime
        val = format_value_neo4j(datetime(2024, 6, 15, 10, 30, 0))
        assert val == '"2024-06-15T10:30:00"'

    def test_list_is_formatted_as_cypher_list(self):
        val = format_value_neo4j([1, None, "x", True])
        assert val == '[1, null, "x", true]'

    def test_unknown_type_becomes_quoted_string(self):
        class Weird:
            def __str__(self): return "weird"
        assert format_value_neo4j(Weird()) == '"weird"'


# ===========================================================================
# 2. Shared schemas
# ===========================================================================

SIMPLE_SCHEMA = """
schema Blog {
    seed: 99
    strategy: random
    combination_strategy: pairwise

    entity Post {
        fields {
            id: uuid
            title: string
            views: number { range 0..1000 }
            published: boolean
        }
        config { generate: 5 }
    }
}
"""

ENUM_SCHEMA = """
schema Shop {
    seed: 1
    strategy: random

    entity Product {
        fields {
            id: uuid
            status: enum["active", "inactive", "archived"]
        }
        config { generate: 6 }
    }
}
"""

FK_SCHEMA = """
schema App {
    seed: 7
    strategy: random

    entity Author {
        fields {
            id: uuid
            name: fullName
        }
        config { generate: 3 }
    }

    entity Article {
        fields {
            id: uuid
            author: ref Author
            headline: string
        }
        config { generate: 5 }
    }
}
"""

INCLUDE_SCHEMA = """
schema Reg {
    seed: 5
    strategy: random

    entity User {
        fields {
            id: uuid
            email: email
            age: number { range 18..99 }
        }
        config {
            generate: 10
            include: [
                { email: "admin@example.com", age: 30 },
                { email: null, age: 18 }
            ]
        }
    }
}
"""

EDGE_CASE_SCHEMA = """
schema Edge {
    seed: 42
    strategy: random

    entity Item {
        fields {
            id: uuid
            label: string { include[null, empty] }
            score: number { range 0..10 }
        }
        config { generate: 8 }
    }
}
"""

FULL_SCHEMA = """
schema Ecommerce {
    seed: 12345
    strategy: smart
    combination_strategy: pairwise

    entity Customer {
        fields {
            id: uuid
            email: email { include[null, invalid] }
            age: number { range 18..80, boundary, partition 3 }
            status: enum["active", "inactive", "banned"]
        }
        config { generate: 20 }
    }

    entity Order {
        fields {
            id: uuid
            customer: ref Customer
            total: number { range 1..500, boundary }
            status: enum["pending", "shipped", "delivered"]
        }
        config { generate: 10 }
    }
}
"""


# ===========================================================================
# 3. Valid Cypher output structure
# ===========================================================================

class TestValidCypherOutput:
    def _render(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return Neo4JGenerator(model, **kwargs).render()

    def test_output_contains_create_statements(self):
        output = self._render(SIMPLE_SCHEMA)
        assert "CREATE" in output
        assert "(:Post" in output

    def test_output_contains_metadata_comments(self):
        output = self._render(SIMPLE_SCHEMA)
        assert "Blog" in output
        assert "//" in output

    def test_fk_generates_relationships(self):
        output = self._render(FK_SCHEMA)
        assert "(:Author" in output
        assert "(:Article" in output
        assert "MATCH" in output
        assert "CREATE" in output


# ===========================================================================
# 4. Metadata structure
# ===========================================================================

class TestMetadata:
    def _render(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return Neo4JGenerator(model, **kwargs).render()

    def test_metadata_schema_name_present(self):
        output = self._render(SIMPLE_SCHEMA)
        assert "Blog" in output

    def test_metadata_seed_present(self):
        output = self._render(SIMPLE_SCHEMA)
        assert "99" in output

    def test_metadata_seed_override(self):
        output = self._render(SIMPLE_SCHEMA, seed=1234)
        assert "1234" in output

    def test_metadata_generated_at_present(self):
        output = self._render(SIMPLE_SCHEMA, timestamp="2024-01-15T10:30:00")
        assert "2024-01-15T10:30:00" in output


# ===========================================================================
# 5. Entity & Node structure
# ===========================================================================

class TestEntityStructure:
    def _render(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return Neo4JGenerator(model, **kwargs).render()

    def test_entity_label_is_created(self):
        output = self._render(SIMPLE_SCHEMA)
        assert "(:Post" in output

    def test_entity_record_count(self):
        output = self._render(SIMPLE_SCHEMA)
        assert output.count("(:Post") == 5

    def test_entity_record_has_all_fields(self):
        output = self._render(SIMPLE_SCHEMA)
        assert "id:" in output
        assert "title:" in output
        assert "views:" in output
        assert "published:" in output

    def test_multiple_entities_present(self):
        output = self._render(FK_SCHEMA)
        assert "(:Author" in output
        assert "(:Article" in output
        assert output.count("(:Author") == 3
        assert output.count("(:Article") == 5


# ===========================================================================
# 6. Data types in Cypher node attributes
# ===========================================================================

class TestDataTypes:
    def _render(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return Neo4JGenerator(model, **kwargs).render()

    def test_uuid_is_quoted_string(self):
        output = self._render(SIMPLE_SCHEMA)
        uuid_re = re.compile(
            r'"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"'
        )
        assert uuid_re.search(output)

    def test_boolean_is_literal(self):
        output = self._render(SIMPLE_SCHEMA)
        assert "true" in output or "false" in output

    def test_number_is_numeric_literal(self):
        output = self._render(SIMPLE_SCHEMA)
        views_re = re.compile(r"views:\s*\d+")
        assert views_re.search(output)

    def test_string_field_is_quoted(self):
        output = self._render(SIMPLE_SCHEMA)
        title_re = re.compile(r'title:\s*"[^"]*"')
        assert title_re.search(output)

    def test_enum_value_in_allowed_set(self):
        model = load_model_from_str(ENUM_SCHEMA)
        output = Neo4JGenerator(model).render()
        assert '"active"' in output or '"inactive"' in output or '"archived"' in output

    def test_null_serialises_to_cypher_null(self):
        model = load_model_from_str(INCLUDE_SCHEMA)
        output = Neo4JGenerator(model).render()
        assert "null" in output


# ===========================================================================
# 7. Null and edge case handling
# ===========================================================================

class TestNullAndEdgeCases:
    def _render(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return Neo4JGenerator(model, **kwargs).render()

    def test_include_null_value_is_cypher_null(self):
        output = self._render(INCLUDE_SCHEMA)
        assert "null" in output

    def test_include_explicit_value_present(self):
        output = self._render(INCLUDE_SCHEMA)
        assert "admin@example.com" in output

    def test_edge_case_empty_string(self):
        output = self._render(EDGE_CASE_SCHEMA)
        assert "''" in output or "null" in output

    def test_no_ref_sentinels_in_output(self):
        output = self._render(FK_SCHEMA)
        assert "__ref__" not in output


# ===========================================================================
# 8. Foreign key & Relationship handling
# ===========================================================================

# ===========================================================================
# 8. Foreign key & Relationship handling
# ===========================================================================

class TestForeignKeysAndRelationships:
    def _render(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return Neo4JGenerator(model, **kwargs).render()

    def test_article_author_relationship_generated(self):
        output = self._render(FK_SCHEMA)
        assert "MATCH" in output
        assert "CREATE" in output
        assert "Author" in output
        assert "Article" in output

    def test_match_references_correct_node_id(self):
        output = self._render(FK_SCHEMA)
        assert "MATCH" in output
        assert "id:" in output or "author" in output


# ===========================================================================
# 9. Seed reproducibility
# ===========================================================================

class TestSeedReproducibility:
    def _render(self, schema_str, seed):
        model = load_model_from_str(schema_str)
        return Neo4JGenerator(model, seed=seed).render()

    def test_same_seed_same_output(self):
        out1 = self._render(SIMPLE_SCHEMA, seed=42)
        out2 = self._render(SIMPLE_SCHEMA, seed=42)
        assert out1 == out2

    def test_different_seeds_different_output(self):
        out1 = self._render(SIMPLE_SCHEMA, seed=1)
        out2 = self._render(SIMPLE_SCHEMA, seed=2)
        assert out1 != out2

    def test_seed_from_schema_used_when_not_overridden(self):
        model = load_model_from_str(SIMPLE_SCHEMA)
        gen1 = Neo4JGenerator(model)
        gen2 = Neo4JGenerator(model)
        assert gen1.render() == gen2.render()


# ===========================================================================
# 10. Integration test — full schema
# ===========================================================================

class TestNeo4jGeneratorIntegration:
    def _render(self, **kwargs):
        model = load_model_from_str(FULL_SCHEMA)
        return Neo4JGenerator(model, **kwargs).render()

    def test_renders_without_error(self):
        output = self._render()
        assert isinstance(output, str)
        assert len(output) > 0

    def test_output_is_valid_cypher_structure(self):
        output = self._render()
        assert "CREATE" in output
        assert "MATCH" in output

    def test_both_entities_present(self):
        output = self._render()
        assert "(:Customer" in output
        assert "(:Order" in output

    def test_customer_record_count(self):
        output = self._render()
        assert output.count("(:Customer") == 20

    def test_order_record_count(self):
        output = self._render()
        assert output.count("(:Order") == 10

    def test_no_ref_sentinels(self):
        output = self._render()
        assert "__ref__" not in output

    def test_null_present_from_email_include(self):
        output = self._render()
        assert "null" in output

    def test_metadata_correct(self):
        output = self._render(timestamp="TEST")
        assert "Ecommerce" in output
        assert "12345" in output
        assert "TEST" in output
