"""
Unit tests for testdatagen/generators/csv_generator.py  (#XX)

Run with:
    pytest tests/test_csv_generator.py -v
"""

import re

from datetime import date, datetime

from grammar_loader import load_model_from_str
from testdatagen.generators.csv_generator import (
    CSVGenerator,
    format_value_csv,
)

# ===========================================================================
# 1. format_value_csv — type conversion
# ===========================================================================

class TestFormatValueCSV:

    def test_none_becomes_empty_string(self):
        assert format_value_csv(None) == ""

    def test_true_becomes_true_string(self):
        assert format_value_csv(True) == "true"

    def test_false_becomes_false_string(self):
        assert format_value_csv(False) == "false"

    def test_bool_not_treated_as_int(self):
        assert format_value_csv(True) == "true"
        assert format_value_csv(False) == "false"

    def test_integer_stays_integer(self):
        value = format_value_csv(42)
        assert value == 42
        assert isinstance(value, int)

    def test_float_stays_float(self):
        value = format_value_csv(3.14)
        assert value == 3.14
        assert isinstance(value, float)

    def test_zero_stays_integer(self):
        assert format_value_csv(0) == 0

    def test_negative_number(self):
        assert format_value_csv(-7) == -7

    def test_string_stays_string(self):
        assert format_value_csv("hello") == "hello"

    def test_empty_string(self):
        assert format_value_csv("") == ""

    def test_string_with_special_chars(self):
        value = format_value_csv('it\'s a "test"')
        assert value == 'it\'s a "test"'

    def test_date_becomes_iso_string(self):
        value = format_value_csv(date(2024, 6, 15))
        assert value == "2024-06-15"

    def test_datetime_becomes_iso_string(self):
        value = format_value_csv(datetime(2024, 6, 15, 10, 30, 0))
        assert value == "2024-06-15T10:30:00"

    def test_list_becomes_semicolon_separated_string(self):
        value = format_value_csv(["a", "b", "c"])
        assert value == "a;b;c"

    def test_list_with_mixed_values(self):
        value = format_value_csv([1, None, True, "abc"])
        assert value == "1;;true;abc"

    def test_empty_list_becomes_empty_string(self):
        assert format_value_csv([]) == ""

    def test_unknown_type_becomes_string(self):
        class Weird:
            def __str__(self):
                return "weird"

        assert format_value_csv(Weird()) == "weird"

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

BOUNDARY_SCHEMA = """
schema BVA {
    seed: 3
    strategy: boundary

    entity Score {
        fields {
            id: uuid
            points: number { range 0..100, boundary }
        }
        config { generate: 20 }
    }
}
"""

ARRAY_REF_SCHEMA = """
schema University {
    seed: 11
    strategy: random

    entity Course {
        fields {
            id: uuid
            title: string
        }
        config { generate: 5 }
    }

    entity Student {
        fields {
            id: uuid
            name: fullName
            courses: ref Course[] count 1..3
        }
        config { generate: 10 }
    }
}
"""

# ===========================================================================
# 3. Build structure
# ===========================================================================

class TestBuildStructure:

    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return CSVGenerator(model, **kwargs).build()

    def test_build_returns_dictionary(self):
        data = self._build(SIMPLE_SCHEMA)
        assert isinstance(data, dict)

    def test_metadata_present(self):
        data = self._build(SIMPLE_SCHEMA)
        assert "metadata" in data

    def test_entities_present(self):
        data = self._build(SIMPLE_SCHEMA)
        assert "entities" in data

    def test_entities_is_dictionary(self):
        data = self._build(SIMPLE_SCHEMA)
        assert isinstance(data["entities"], dict)


# ===========================================================================
# 4. Metadata structure
# ===========================================================================

class TestMetadata:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return CSVGenerator(model, **kwargs).build()

    def test_metadata_key_present(self):
        data = self._build(SIMPLE_SCHEMA)
        assert "metadata" in data

    def test_metadata_schema_name(self):
        data = self._build(SIMPLE_SCHEMA)
        assert data["metadata"]["schema"] == "Blog"

    def test_metadata_seed(self):
        data = self._build(SIMPLE_SCHEMA)
        assert data["metadata"]["seed"] == 99

    def test_metadata_seed_override(self):
        data = self._build(SIMPLE_SCHEMA, seed=1234)
        assert data["metadata"]["seed"] == 1234

    def test_metadata_generated_at(self):
        data = self._build(SIMPLE_SCHEMA, timestamp="2024-01-15T10:30:00")
        assert data["metadata"]["generated_at"] == "2024-01-15T10:30:00"

    def test_metadata_generated_at_empty_default(self):
        data = self._build(SIMPLE_SCHEMA)
        assert "generated_at" in data["metadata"]

    def test_entities_key_present(self):
        data = self._build(SIMPLE_SCHEMA)
        assert "entities" in data

    def test_metadata_is_dictionary(self):
        data = self._build(SIMPLE_SCHEMA)
        assert isinstance(data["metadata"], dict)
        
    def test_metadata_contains_expected_keys(self):
        data = self._build(SIMPLE_SCHEMA)

        assert set(data["metadata"]) == {
            "schema",
            "seed",
            "generated_at",
        }


# ===========================================================================
# 5. Entity structure
# ===========================================================================

class TestEntityStructure:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return CSVGenerator(model, **kwargs).build()

    def test_entity_name_is_key(self):
        data = self._build(SIMPLE_SCHEMA)
        assert "Post" in data["entities"]

    def test_entity_value_is_list(self):
        data = self._build(SIMPLE_SCHEMA)
        assert isinstance(data["entities"]["Post"], list)

    def test_entity_record_count(self):
        data = self._build(SIMPLE_SCHEMA)
        assert len(data["entities"]["Post"]) == 5

    def test_entity_record_is_dict(self):
        data = self._build(SIMPLE_SCHEMA)
        record = data["entities"]["Post"][0]
        assert isinstance(record, dict)

    def test_entity_record_has_all_fields(self):
        data = self._build(SIMPLE_SCHEMA)
        record = data["entities"]["Post"][0]
        assert "id" in record
        assert "title" in record
        assert "views" in record
        assert "published" in record

    def test_multiple_entities_present(self):
        data = self._build(FK_SCHEMA)
        assert "Author" in data["entities"]
        assert "Article" in data["entities"]


# ===========================================================================
# 6. Data types in CSV records
# ===========================================================================

class TestDataTypes:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return CSVGenerator(model, **kwargs).build()

    def test_uuid_is_string(self):
        data = self._build(SIMPLE_SCHEMA)
        for record in data["entities"]["Post"]:
            assert isinstance(record["id"], str)

    def test_uuid_format(self):
        data = self._build(SIMPLE_SCHEMA)
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        for record in data["entities"]["Post"]:
            assert uuid_re.match(record["id"]), f"Bad UUID: {record['id']!r}"

    def test_boolean_is_string(self):
        data = self._build(SIMPLE_SCHEMA)

        for record in data["entities"]["Post"]:
            assert record["published"] in {"true", "false"}

    def test_boolean_type_is_string(self):
        data = self._build(SIMPLE_SCHEMA)

        for record in data["entities"]["Post"]:
            assert isinstance(record["published"], str)

    def test_number_is_numeric(self):
        data = self._build(SIMPLE_SCHEMA)
        for record in data["entities"]["Post"]:
            assert isinstance(record["views"], (int, float))

    def test_string_field_is_string(self):
        data = self._build(SIMPLE_SCHEMA)
        for record in data["entities"]["Post"]:
            assert isinstance(record["title"], str)

    def test_enum_value_in_allowed_set(self):
        data = self._build(ENUM_SCHEMA)
        allowed = {"active", "inactive", "archived"}
        for record in data["entities"]["Product"]:
            assert record["status"] in allowed

    def test_null_becomes_empty_string(self):
        data = self._build(INCLUDE_SCHEMA)
        records = data["entities"]["User"]
        empty_records = [
            r for r in records
            if r.get("email") == ""
        ]
        assert empty_records

    def test_array_ref_is_semicolon_string(self):
        data = self._build(ARRAY_REF_SCHEMA)
        students = data["entities"]["Student"]
        for student in students:
            value = student["courses"]
            assert isinstance(value, str)
            if value:
                assert ";" in value or len(value) > 0

    def test_array_ref_never_returns_python_list(self):
        data = self._build(ARRAY_REF_SCHEMA)
        for student in data["entities"]["Student"]:
            assert not isinstance(student["courses"], list)

## ===========================================================================
# 7. Null and edge case handling
# ===========================================================================

class TestNullAndEdgeCases:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return CSVGenerator(model, **kwargs).build()

    def test_include_null_value_becomes_empty_string(self):
        data = self._build(INCLUDE_SCHEMA)
        records = data["entities"]["User"]
        emails = [r["email"] for r in records]
        assert "" in emails

    def test_include_explicit_value_present(self):
        data = self._build(INCLUDE_SCHEMA)
        emails = [r["email"] for r in data["entities"]["User"]]
        assert "admin@example.com" in emails

    def test_edge_case_empty_string(self):
        data = self._build(EDGE_CASE_SCHEMA)
        labels = [r["label"] for r in data["entities"]["Item"]]
        assert "" in labels

    def test_no_ref_sentinels_in_output(self):
        data = self._build(FK_SCHEMA)
        for entity_records in data["entities"].values():
            for record in entity_records:
                for value in record.values():
                    assert value != "__ref__"

# ===========================================================================
# 8. Foreign key handling
# ===========================================================================

class TestForeignKeys:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return CSVGenerator(model, **kwargs).build()

    def test_author_before_article_in_entities(self):
        data = self._build(FK_SCHEMA)
        keys = list(data["entities"].keys())
        assert keys.index("Author") < keys.index("Article")

    def test_article_author_field_is_uuid_string(self):
        data = self._build(FK_SCHEMA)
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        for record in data["entities"]["Article"]:
            author = record["author"]
            if author != "":
                assert uuid_re.match(author)

    def test_article_author_exists_in_authors(self):
        data = self._build(FK_SCHEMA)
        author_ids = {
            r["id"]
            for r in data["entities"]["Author"]
        }
        for record in data["entities"]["Article"]:
            author = record["author"]
            if author != "":
                assert author in author_ids

# ===========================================================================
# 9. Seed reproducibility
# ===========================================================================

class TestSeedReproducibility:
    def _build(self, schema_str, seed):
        model = load_model_from_str(schema_str)
        return CSVGenerator(model, seed=seed).build()

    def test_same_seed_same_output(self):
        d1 = self._build(SIMPLE_SCHEMA, seed=42)
        d2 = self._build(SIMPLE_SCHEMA, seed=42)
        assert d1 == d2

    def test_different_seeds_different_output(self):
        d1 = self._build(SIMPLE_SCHEMA, seed=1)
        d2 = self._build(SIMPLE_SCHEMA, seed=2)
        assert d1 != d2

    def test_seed_from_schema_used_when_not_overridden(self):
        model = load_model_from_str(SIMPLE_SCHEMA)
        gen1 = CSVGenerator(model)
        gen2 = CSVGenerator(model)
        assert gen1.build() == gen2.build()


# ===========================================================================
# 10. Integration test — full schema
# ===========================================================================

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

class TestCSVGeneratorIntegration:
    def _build(self):
        model = load_model_from_str(FULL_SCHEMA)
        return CSVGenerator(model, timestamp="TEST").build()

    def test_renders_without_error(self):
        data = self._build()
        assert isinstance(data, dict)

    def test_output_structure(self):
        data = self._build()
        assert "metadata" in data
        assert "entities" in data

    def test_both_entities_present(self):
        data = self._build()
        assert "Customer" in data["entities"]
        assert "Order" in data["entities"]

    def test_customer_record_count(self):
        data = self._build()
        assert len(data["entities"]["Customer"]) == 20

    def test_order_record_count(self):
        data = self._build()
        assert len(data["entities"]["Order"]) == 10

    def test_customer_before_order(self):
        data = self._build()
        keys = list(data["entities"].keys())
        assert keys.index("Customer") < keys.index("Order")

    def test_no_ref_sentinels(self):
        data = self._build()
        for records in data["entities"].values():
            for record in records:
                for val in record.values():
                    assert val != "__ref__"

    def test_null_present_from_email_include(self):
        data = self._build()
        emails = [
            r["email"]
            for r in data["entities"]["Customer"]
        ]
        assert "" in emails

    def test_order_customer_fk_valid(self):
        data = self._build()
        customer_ids = {
            r["id"]
            for r in data["entities"]["Customer"]
        }
        for record in data["entities"]["Order"]:
            customer = record["customer"]
            if customer != "":
                assert customer in customer_ids

    def test_metadata_correct(self):
        data = self._build()
        assert data["metadata"]["schema"] == "Ecommerce"
        assert data["metadata"]["seed"] == 12345
        assert data["metadata"]["generated_at"] == "TEST"

    def test_all_values_are_csv_compatible(self):
        data = self._build()
        for records in data["entities"].values():
            for record in records:
                for value in record.values():
                    assert not isinstance(value, list)
