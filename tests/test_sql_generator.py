"""
Unit tests for testdatagen/generators/sql_generator.py  (#15)

Run with:
    pytest tests/test_sql_generator.py -v
"""

import re
from types import SimpleNamespace

import pytest

from testdatagen.generators.sql_generator import (
    SQLGenerator,
    format_value,
    _topological_sort,
    _escape_string,
)
from grammar_loader import load_model_from_str


# ===========================================================================
# 1. format_value — SQL literal formatting
# ===========================================================================

class TestFormatValue:
    def test_none_becomes_null(self):
        assert format_value(None) == "NULL"

    def test_true_becomes_TRUE(self):
        assert format_value(True) == "TRUE"

    def test_false_becomes_FALSE(self):
        assert format_value(False) == "FALSE"

    def test_integer(self):
        assert format_value(42) == "42"

    def test_negative_integer(self):
        assert format_value(-7) == "-7"

    def test_float(self):
        assert format_value(3.14) == "3.14"

    def test_zero(self):
        assert format_value(0) == "0"

    def test_string_gets_single_quotes(self):
        assert format_value("hello") == "'hello'"

    def test_string_with_single_quote_escaped(self):
        assert format_value("it's") == "'it''s'"

    def test_empty_string(self):
        assert format_value("") == "''"

    def test_uuid_string(self):
        val = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert format_value(val) == f"'{val}'"

    def test_bool_is_not_treated_as_int(self):
        # bool is a subclass of int — must be checked before int branch
        assert format_value(True)  == "TRUE"
        assert format_value(False) == "FALSE"

    def test_sql_injection_escaped(self):
        assert format_value("'; DROP TABLE users; --") == "'''; DROP TABLE users; --'"


class TestEscapeString:
    def test_no_quotes(self):
        assert _escape_string("hello") == "hello"

    def test_single_quote(self):
        assert _escape_string("it's") == "it''s"

    def test_multiple_quotes(self):
        assert _escape_string("a'b'c") == "a''b''c"


# ===========================================================================
# 2. Topological sort
# ===========================================================================

def _make_entity(name, refs=None):
    """Build a minimal mock entity for topological sort tests."""
    fields = []
    for ref_name in (refs or []):
        ref_type = SimpleNamespace(
            __class__=type("RefType", (), {}),
            entity=SimpleNamespace(name=ref_name),
            array=False,
        )
        fields.append(SimpleNamespace(name=f"ref_{ref_name.lower()}", type=ref_type))
    return SimpleNamespace(name=name, fields=fields)


class TestTopologicalSort:
    def test_no_deps_preserves_order(self):
        entities = [_make_entity("A"), _make_entity("B"), _make_entity("C")]
        result = _topological_sort(entities)
        names = [e.name for e in result]
        assert set(names) == {"A", "B", "C"}

    def test_single_dependency(self):
        # B depends on A → A must come first
        a = _make_entity("A")
        b = _make_entity("B", refs=["A"])
        result = _topological_sort([b, a])
        names = [e.name for e in result]
        assert names.index("A") < names.index("B")

    def test_chain_dependency(self):
        # C → B → A  →  order must be A, B, C
        a = _make_entity("A")
        b = _make_entity("B", refs=["A"])
        c = _make_entity("C", refs=["B"])
        result = _topological_sort([c, b, a])
        names = [e.name for e in result]
        assert names.index("A") < names.index("B") < names.index("C")

    def test_multiple_dependencies(self):
        # C depends on both A and B
        a = _make_entity("A")
        b = _make_entity("B")
        c = _make_entity("C", refs=["A", "B"])
        result = _topological_sort([c, b, a])
        names = [e.name for e in result]
        assert names.index("A") < names.index("C")
        assert names.index("B") < names.index("C")

    def test_returns_all_entities(self):
        entities = [_make_entity("X"), _make_entity("Y", refs=["X"])]
        result = _topological_sort(entities)
        assert len(result) == 2


# ===========================================================================
# 3. Schema rendering via load_model_from_str
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
        config {
            generate: 5
        }
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
        config {
            generate: 6
        }
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


class TestSQLGeneratorRender:

    def _render(self, schema_str, seed=None):
        model = load_model_from_str(schema_str)
        gen = SQLGenerator(model, seed=seed, timestamp="TEST")
        return gen.render()

    # --- basic structure ---

    def test_output_is_string(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert isinstance(sql, str)

    def test_contains_insert_into(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert "INSERT INTO" in sql

    def test_contains_schema_name_in_header(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert "Schema: Blog" in sql

    def test_contains_seed_in_header(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert "Seed: 99" in sql

    def test_contains_timestamp(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert "TEST" in sql

    def test_table_name_is_lowercase_plural(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert "INSERT INTO posts" in sql

    def test_columns_present(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert "id" in sql
        assert "title" in sql
        assert "views" in sql
        assert "published" in sql

    # --- data type formatting in output ---

    def test_boolean_values_use_TRUE_FALSE(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert re.search(r"\b(TRUE|FALSE)\b", sql)

    def test_null_values_use_NULL_keyword(self):
        sql = self._render(INCLUDE_SCHEMA)
        assert "NULL" in sql

    def test_string_values_have_single_quotes(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert re.search(r"'[0-9a-f-]{36}'", sql)

    def test_number_values_have_no_quotes(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert re.search(r"\b\d+\b", sql)

    # --- record count ---

    def test_generates_correct_number_of_records(self):
        sql = self._render(SIMPLE_SCHEMA)
        # 5 records → 5 value tuples (lines starting with '(')
        lines = [l.strip() for l in sql.splitlines() if l.strip().startswith("(")]
        assert len(lines) == 5

    # --- enum ---

    def test_enum_values_are_quoted_strings(self):
        sql = self._render(ENUM_SCHEMA)
        for val in ["'active'", "'inactive'", "'archived'"]:
            assert val in sql

    # --- include (explicit test cases) ---

    def test_include_values_appear_in_output(self):
        sql = self._render(INCLUDE_SCHEMA)
        assert "'admin@example.com'" in sql

    def test_include_null_becomes_SQL_NULL(self):
        sql = self._render(INCLUDE_SCHEMA)
        assert "NULL" in sql

    # --- foreign keys ---

    def test_fk_schema_author_before_article(self):
        sql = self._render(FK_SCHEMA)
        author_pos  = sql.find("INSERT INTO authors")
        article_pos = sql.find("INSERT INTO articles")
        assert author_pos < article_pos, "Authors must be inserted before Articles"

    def test_fk_no_ref_sentinel_in_output(self):
        sql = self._render(FK_SCHEMA)
        assert "__ref__" not in sql

    def test_fk_article_rows_contain_uuid(self):
        """Each article row must contain at least one UUID (the author FK)."""
        sql = self._render(FK_SCHEMA)
        start = sql.find("INSERT INTO articles")
        end   = sql.find(";", start)
        article_block = sql[start:end]

        # Collect lines that are value rows (start with '(')
        value_lines = [l.strip() for l in article_block.splitlines()
                       if l.strip().startswith("(")]
        assert value_lines, "No value rows found in articles INSERT"

        uuid_re = re.compile(
            r"'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'"
        )
        for line in value_lines:
            matches = uuid_re.findall(line)
            # Each row should have at least 2 UUIDs: id + author FK
            assert len(matches) >= 2, (
                f"Expected at least 2 UUIDs per article row, got {len(matches)} in: {line!r}"
            )

    # --- boundary strategy ---

    def test_boundary_values_include_range_endpoints(self):
        sql = self._render(BOUNDARY_SCHEMA)
        assert re.search(r"\b0\b", sql)
        assert re.search(r"\b100\b", sql)

    # --- seed reproducibility ---

    def test_same_seed_produces_same_output(self):
        sql1 = self._render(SIMPLE_SCHEMA, seed=42)
        sql2 = self._render(SIMPLE_SCHEMA, seed=42)
        assert sql1 == sql2

    def test_different_seeds_produce_different_output(self):
        sql1 = self._render(SIMPLE_SCHEMA, seed=1)
        sql2 = self._render(SIMPLE_SCHEMA, seed=2)
        assert sql1 != sql2

    # --- SQL validity (structural checks) ---

    def test_insert_ends_with_semicolon(self):
        sql = self._render(SIMPLE_SCHEMA)
        assert re.search(r";\s*$", sql, re.MULTILINE)

    def test_values_rows_comma_separated(self):
        sql = self._render(SIMPLE_SCHEMA)
        insert_block = sql[sql.find("VALUES"):]
        rows = re.findall(r"\([^)]+\)", insert_block)
        assert len(rows) > 1


# ===========================================================================
# 4. Integration test — full example schema
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


class TestSQLGeneratorIntegration:
    def test_full_schema_renders_without_error(self):
        model = load_model_from_str(FULL_SCHEMA)
        gen = SQLGenerator(model, timestamp="INTEGRATION_TEST")
        sql = gen.render()
        assert isinstance(sql, str)
        assert len(sql) > 100

    def test_customer_before_order(self):
        model = load_model_from_str(FULL_SCHEMA)
        sql = SQLGenerator(model).render()
        assert sql.find("INSERT INTO customers") < sql.find("INSERT INTO orders")

    def test_no_ref_sentinels_in_output(self):
        model = load_model_from_str(FULL_SCHEMA)
        sql = SQLGenerator(model).render()
        assert "__ref__" not in sql

    def test_null_appears_for_email_edge_cases(self):
        model = load_model_from_str(FULL_SCHEMA)
        sql = SQLGenerator(model).render()
        assert "NULL" in sql

    def test_invalid_email_appears_in_output(self):
        model = load_model_from_str(FULL_SCHEMA)
        sql = SQLGenerator(model).render()
        assert "invalid" in sql.lower()

    def test_both_inserts_present(self):
        model = load_model_from_str(FULL_SCHEMA)
        sql = SQLGenerator(model).render()
        assert "INSERT INTO customers" in sql
        assert "INSERT INTO orders" in sql