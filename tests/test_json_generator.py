"""
Unit tests for testdatagen/generators/json_generator.py  (#16)

Run with:
    pytest tests/test_json_generator.py -v
"""

import json
import re

import pytest

from testdatagen.generators.json_generator import JSONGenerator, format_value_json
from grammar_loader import load_model_from_str


# ===========================================================================
# 1. format_value_json — type conversion
# ===========================================================================

class TestFormatValueJson:
    def test_none_stays_none(self):
        assert format_value_json(None) is None

    def test_true_stays_bool(self):
        assert format_value_json(True) is True
        assert isinstance(format_value_json(True), bool)

    def test_false_stays_bool(self):
        assert format_value_json(False) is False

    def test_bool_not_treated_as_int(self):
        # bool is subclass of int — must stay as bool not become 1/0
        assert format_value_json(True)  is True
        assert format_value_json(False) is False

    def test_integer_stays_int(self):
        val = format_value_json(42)
        assert val == 42
        assert isinstance(val, int)

    def test_float_stays_float(self):
        val = format_value_json(3.14)
        assert val == 3.14
        assert isinstance(val, float)

    def test_zero_stays_int(self):
        assert format_value_json(0) == 0

    def test_negative_number(self):
        assert format_value_json(-7) == -7

    def test_string_stays_string(self):
        assert format_value_json("hello") == "hello"

    def test_empty_string(self):
        assert format_value_json("") == ""

    def test_string_with_special_chars(self):
        # No escaping needed — json.dumps handles that
        val = format_value_json("it's a \"test\"")
        assert val == "it's a \"test\""

    def test_date_becomes_iso_string(self):
        from datetime import date
        val = format_value_json(date(2024, 6, 15))
        assert val == "2024-06-15"

    def test_datetime_becomes_iso_string(self):
        from datetime import datetime
        val = format_value_json(datetime(2024, 6, 15, 10, 30, 0))
        assert val == "2024-06-15T10:30:00"

    def test_list_is_recursively_formatted(self):
        val = format_value_json([1, None, "x", True])
        assert val == [1, None, "x", True]

    def test_unknown_type_becomes_string(self):
        class Weird:
            def __str__(self): return "weird"
        assert format_value_json(Weird()) == "weird"


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


# ===========================================================================
# 3. Valid JSON output
# ===========================================================================

class TestValidJson:
    def _render(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return JSONGenerator(model, **kwargs).render()

    def test_output_is_valid_json(self):
        output = self._render(SIMPLE_SCHEMA)
        parsed = json.loads(output)   # must not raise
        assert parsed is not None

    def test_compact_output_is_valid_json(self):
        output = self._render(SIMPLE_SCHEMA, pretty=False)
        parsed = json.loads(output)
        assert parsed is not None

    def test_pretty_output_has_indentation(self):
        output = self._render(SIMPLE_SCHEMA, pretty=True, indent=2)
        assert "\n" in output
        assert "  " in output

    def test_compact_output_has_no_newlines(self):
        output = self._render(SIMPLE_SCHEMA, pretty=False)
        assert "\n" not in output

    def test_custom_indent(self):
        output = self._render(SIMPLE_SCHEMA, pretty=True, indent=4)
        assert "    " in output   # 4-space indent


# ===========================================================================
# 4. Metadata structure
# ===========================================================================

class TestMetadata:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return JSONGenerator(model, **kwargs).build()

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


# ===========================================================================
# 5. Entity structure
# ===========================================================================

class TestEntityStructure:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return JSONGenerator(model, **kwargs).build()

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
# 6. Data types in JSON records
# ===========================================================================

class TestDataTypes:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return JSONGenerator(model, **kwargs).build()

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

    def test_boolean_is_python_bool(self):
        data = self._build(SIMPLE_SCHEMA)
        for record in data["entities"]["Post"]:
            assert isinstance(record["published"], bool)

    def test_boolean_not_int(self):
        data = self._build(SIMPLE_SCHEMA)
        for record in data["entities"]["Post"]:
            # bool is subclass of int, but type() must be exactly bool
            assert type(record["published"]) is bool

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

    def test_null_is_python_none(self):
        data = self._build(INCLUDE_SCHEMA)
        records = data["entities"]["User"]
        null_records = [r for r in records if r.get("email") is None]
        assert null_records, "Expected at least one null email from include"

    def test_null_serialises_to_json_null(self):
        model = load_model_from_str(INCLUDE_SCHEMA)
        output = JSONGenerator(model).render()
        assert '"email": null' in output or '"email":null' in output


# ===========================================================================
# 7. Null and edge case handling
# ===========================================================================

class TestNullAndEdgeCases:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return JSONGenerator(model, **kwargs).build()

    def test_include_null_value_is_none(self):
        data = self._build(INCLUDE_SCHEMA)
        records = data["entities"]["User"]
        emails = [r["email"] for r in records]
        assert None in emails

    def test_include_explicit_value_present(self):
        data = self._build(INCLUDE_SCHEMA)
        emails = [r["email"] for r in data["entities"]["User"]]
        assert "admin@example.com" in emails

    def test_edge_case_empty_string(self):
        data = self._build(EDGE_CASE_SCHEMA)
        labels = [r["label"] for r in data["entities"]["Item"]]
        assert "" in labels or None in labels   # empty or null from include

    def test_no_ref_sentinels_in_output(self):
        data = self._build(FK_SCHEMA)
        for entity_records in data["entities"].values():
            for record in entity_records:
                for val in record.values():
                    assert val != "__ref__", f"Found __ref__ sentinel in output: {record}"


# ===========================================================================
# 8. Foreign key handling
# ===========================================================================

class TestForeignKeys:
    def _build(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return JSONGenerator(model, **kwargs).build()

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
            author_val = record["author"]
            if author_val is not None:
                assert uuid_re.match(str(author_val)), (
                    f"author FK is not a UUID: {author_val!r}"
                )

    def test_article_author_exists_in_authors(self):
        data = self._build(FK_SCHEMA)
        author_ids = {r["id"] for r in data["entities"]["Author"]}
        for record in data["entities"]["Article"]:
            if record["author"] is not None:
                assert record["author"] in author_ids, (
                    f"Article references unknown author: {record['author']!r}"
                )


# ===========================================================================
# 9. Seed reproducibility
# ===========================================================================

class TestSeedReproducibility:
    def _build(self, schema_str, seed):
        model = load_model_from_str(schema_str)
        return JSONGenerator(model, seed=seed).build()

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
        gen1 = JSONGenerator(model)
        gen2 = JSONGenerator(model)
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


class TestJSONGeneratorIntegration:
    def _build(self):
        model = load_model_from_str(FULL_SCHEMA)
        return JSONGenerator(model, timestamp="TEST").build()

    def test_renders_without_error(self):
        data = self._build()
        assert isinstance(data, dict)

    def test_output_is_valid_json(self):
        model = load_model_from_str(FULL_SCHEMA)
        output = JSONGenerator(model).render()
        json.loads(output)   # must not raise

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
        emails = [r["email"] for r in data["entities"]["Customer"]]
        assert None in emails

    def test_order_customer_fk_valid(self):
        data = self._build()
        customer_ids = {r["id"] for r in data["entities"]["Customer"]}
        for record in data["entities"]["Order"]:
            if record["customer"] is not None:
                assert record["customer"] in customer_ids

    def test_metadata_correct(self):
        data = self._build()
        assert data["metadata"]["schema"] == "Ecommerce"
        assert data["metadata"]["seed"] == 12345
        assert data["metadata"]["generated_at"] == "TEST"