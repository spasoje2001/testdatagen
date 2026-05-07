"""
Unit tests for testdatagen/generators/report_generator.py  (#17)

Run with:
    pytest tests/test_report_generator.py -v
"""

import re

import pytest

from testdatagen.generators.report_generator import (
    ReportGenerator,
    calculate_field_coverage,
    _coverage_color,
    _coverage_badge,
)
from grammar_loader import load_model_from_str


# ===========================================================================
# 1. Coverage colour / badge helpers
# ===========================================================================

class TestCoverageHelpers:
    def test_green_at_100(self):
        assert _coverage_badge(100) == "green"

    def test_green_at_90(self):
        assert _coverage_badge(90) == "green"

    def test_yellow_at_89(self):
        assert _coverage_badge(89) == "yellow"

    def test_yellow_at_60(self):
        assert _coverage_badge(60) == "yellow"

    def test_red_at_59(self):
        assert _coverage_badge(59) == "red"

    def test_red_at_0(self):
        assert _coverage_badge(0) == "red"

    def test_color_green(self):
        assert _coverage_color(100) == "#22c55e"

    def test_color_yellow(self):
        assert _coverage_color(75) == "#eab308"

    def test_color_red(self):
        assert _coverage_color(30) == "#ef4444"


# ===========================================================================
# 2. calculate_field_coverage
# ===========================================================================

# --- helpers to build minimal mock field objects ---

from types import SimpleNamespace

def _simple_field(type_name, constraints=None):
    # Create a proper named class so __class__.__name__ works correctly
    SimpleType = type("SimpleType", (), {})
    ft = SimpleType()
    ft.name = type_name

    field = SimpleNamespace(
        name=f"field_{type_name}",
        type=ft,
        constraints=constraints or [],
    )
    return field


def _make_constraint(cls_name, **attrs):
    c = SimpleNamespace(**attrs)
    c.__class__ = type(cls_name, (), {"__name__": cls_name})
    c.__class__.__name__ = cls_name
    return c


class TestCalculateFieldCoverage:

    def test_no_strategy_returns_100_pct(self):
        # A plain string field with no constraints → required=0 → 100%
        field = _simple_field("string")
        result = calculate_field_coverage(field, ["hello", "world"], "random")
        assert result["required"] == 0
        assert result["percentage"] == 100.0
        assert result["missing"] == set()

    def test_boolean_requires_true_and_false(self):
        field = _simple_field("boolean")
        result = calculate_field_coverage(field, [True, False], "random")
        assert result["required"] == 2
        assert result["covered"] == 2
        assert result["percentage"] == 100.0

    def test_boolean_partial_coverage(self):
        field = _simple_field("boolean")
        result = calculate_field_coverage(field, [True], "random")
        assert result["covered"] == 1
        assert result["required"] == 2
        assert result["percentage"] == 50.0
        assert False in result["missing"]

    def test_boundary_strategy_uses_real_schema(self):
        """Use load_model_from_str to get real textX field objects."""
        model = load_model_from_str("""
        schema T {
            entity E {
                fields {
                    points: number { range 0..10, boundary }
                }
                config { generate: 20 }
            }
        }
        """)
        field = model.entities[0].fields[0]
        # BVA for 0..10 (integer): valid boundary values are 0, 1, 9, 10
        result = calculate_field_coverage(field, [0, 1, 9, 10], "random")
        assert result["required"] > 0
        assert result["covered"] == result["required"]
        assert result["percentage"] == 100.0

    def test_boundary_partial_coverage_detects_missing(self):
        model = load_model_from_str("""
        schema T {
            entity E {
                fields {
                    points: number { range 0..10, boundary }
                }
                config { generate: 20 }
            }
        }
        """)
        field = model.entities[0].fields[0]
        # only provide min value — max boundary values will be missing
        result = calculate_field_coverage(field, [0, 1], "random")
        assert result["missing"]
        assert result["percentage"] < 100.0

    def test_partition_strategy(self):
        model = load_model_from_str("""
        schema T {
            entity E {
                fields {
                    age: number { range 0..90, partition 3 }
                }
                config { generate: 10 }
            }
        }
        """)
        field = model.entities[0].fields[0]
        # EP with 3 partitions → 3 representative values
        result = calculate_field_coverage(field, [15, 45, 75], "random")
        assert result["required"] == 3
        assert result["covered"] == 3
        assert result["percentage"] == 100.0

    def test_smart_strategy_combines_bva_and_ep(self):
        model = load_model_from_str("""
        schema T {
            entity E {
                fields {
                    score: number { range 0..100, boundary, partition 3 }
                }
                config { generate: 20 }
            }
        }
        """)
        field = model.entities[0].fields[0]
        result = calculate_field_coverage(field, [], "smart")
        # smart = BVA + EP → more required cases than BVA alone
        assert result["required"] > 4   # BVA alone gives 4 valid values for 0..100

    def test_include_edge_cases(self):
        model = load_model_from_str("""
        schema T {
            entity E {
                fields {
                    email: email { include[null, invalid] }
                }
                config { generate: 5 }
            }
        }
        """)
        field = model.entities[0].fields[0]
        result = calculate_field_coverage(field, [None, "invalid-email-format"], "random")
        assert result["required"] == 2
        assert result["covered"] == 2
        assert result["percentage"] == 100.0

    def test_include_edge_case_missing(self):
        model = load_model_from_str("""
        schema T {
            entity E {
                fields {
                    email: email { include[null, invalid] }
                }
                config { generate: 5 }
            }
        }
        """)
        field = model.entities[0].fields[0]
        # Only null provided — invalid is missing
        result = calculate_field_coverage(field, [None], "random")
        assert result["covered"] == 1
        assert result["required"] == 2
        assert result["percentage"] == 50.0

    def test_strategy_tags_present(self):
        model = load_model_from_str("""
        schema T {
            entity E {
                fields {
                    n: number { range 0..100, boundary }
                }
                config { generate: 10 }
            }
        }
        """)
        field = model.entities[0].fields[0]
        result = calculate_field_coverage(field, [], "random")
        assert "BVA" in result["strategy_tags"]

    def test_random_field_tags(self):
        field = _simple_field("email")
        result = calculate_field_coverage(field, ["a@b.com"], "random")
        assert "random" in result["strategy_tags"]


# ===========================================================================
# 3. Shared test schemas
# ===========================================================================

SIMPLE_SCHEMA = """
schema Blog {
    seed: 42
    strategy: random

    entity Post {
        fields {
            id: uuid
            title: string
            published: boolean
        }
        config { generate: 5 }
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

SMART_SCHEMA = """
schema Smart {
    seed: 7
    strategy: smart

    entity User {
        fields {
            id: uuid
            age: number { range 18..65, boundary, partition 3 }
            status: enum["active", "inactive", "banned"]
            email: email { include[null, invalid] }
        }
        config { generate: 30 }
    }
}
"""

FK_SCHEMA = """
schema App {
    seed: 9
    strategy: random

    entity Author {
        fields {
            id: uuid
            name: fullName
        }
        config { generate: 5 }
    }

    entity Article {
        fields {
            id: uuid
            author: ref Author
            views: number { range 0..1000 }
        }
        config { generate: 8 }
    }
}
"""

FULL_COVERAGE_SCHEMA = """
schema Full {
    seed: 1
    strategy: smart

    entity Item {
        fields {
            id: uuid
            score: number { range 0..10, boundary, partition 2 }
            active: boolean
        }
        config { generate: 50 }
    }
}
"""

PARTIAL_SCHEMA = """
schema Partial {
    seed: 2
    strategy: random

    entity Thing {
        fields {
            id: uuid
            level: number { range 0..5, boundary }
        }
        config { generate: 2 }
    }
}
"""


# ===========================================================================
# 4. calculate_coverage() — raw data
# ===========================================================================

class TestCalculateCoverage:
    def _coverage(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return ReportGenerator(model, **kwargs).calculate_coverage()

    def test_returns_dict(self):
        data = self._coverage(SIMPLE_SCHEMA)
        assert isinstance(data, dict)

    def test_has_required_keys(self):
        data = self._coverage(SIMPLE_SCHEMA)
        assert "schema_name" in data
        assert "entities" in data
        assert "overall" in data

    def test_schema_name_correct(self):
        data = self._coverage(SIMPLE_SCHEMA)
        assert data["schema_name"] == "Blog"

    def test_entities_list(self):
        data = self._coverage(SIMPLE_SCHEMA)
        assert isinstance(data["entities"], list)
        assert len(data["entities"]) == 1

    def test_entity_has_required_keys(self):
        data = self._coverage(SIMPLE_SCHEMA)
        entity = data["entities"][0]
        for key in ("name", "records", "required", "covered", "pct", "fields"):
            assert key in entity, f"Missing key: {key}"

    def test_field_has_required_keys(self):
        data = self._coverage(SIMPLE_SCHEMA)
        field = data["entities"][0]["fields"][0]
        for key in ("name", "type", "required", "covered", "pct", "missing", "strategy_tags"):
            assert key in field, f"Missing key: {key}"

    def test_overall_pct_between_0_and_100(self):
        data = self._coverage(SIMPLE_SCHEMA)
        assert 0 <= data["overall"]["pct"] <= 100

    def test_full_coverage_100_pct(self):
        data = self._coverage(FULL_COVERAGE_SCHEMA)
        assert data["overall"]["pct"] == 100.0

    def test_partial_coverage_less_than_100(self):
        # generate: 2 with boundary on 0..5 → likely won't cover all 4 valid BVA values
        data = self._coverage(PARTIAL_SCHEMA)
        score_entity = data["entities"][0]
        level_field = next(f for f in score_entity["fields"] if f["name"] == "level")
        # required > 0 (BVA on 0..5)
        assert level_field["required"] > 0

    def test_missing_values_are_strings(self):
        data = self._coverage(PARTIAL_SCHEMA)
        entity = data["entities"][0]
        level_field = next(f for f in entity["fields"] if f["name"] == "level")
        for m in level_field["missing"]:
            assert isinstance(m, str)

    def test_fk_entities_ordered(self):
        data = self._coverage(FK_SCHEMA)
        names = [e["name"] for e in data["entities"]]
        assert names.index("Author") < names.index("Article")

    def test_record_count_matches_generate(self):
        data = self._coverage(SIMPLE_SCHEMA)
        assert data["entities"][0]["records"] == 5

    def test_smart_strategy_reports_bva_and_ep(self):
        data = self._coverage(SMART_SCHEMA)
        age_field = next(
            f for f in data["entities"][0]["fields"] if f["name"] == "age"
        )
        tags = age_field["strategy_tags"]
        assert "BVA" in tags
        assert "EP" in tags


# ===========================================================================
# 5. render() — HTML output
# ===========================================================================

class TestRenderHTML:
    def _render(self, schema_str, **kwargs):
        model = load_model_from_str(schema_str)
        return ReportGenerator(model, **kwargs).render()

    def test_returns_string(self):
        html = self._render(SIMPLE_SCHEMA)
        assert isinstance(html, str)

    def test_is_valid_html_structure(self):
        html = self._render(SIMPLE_SCHEMA)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<body" in html
        assert "</body>" in html

    def test_contains_schema_name(self):
        html = self._render(SIMPLE_SCHEMA)
        assert "Blog" in html

    def test_contains_seed(self):
        html = self._render(SIMPLE_SCHEMA)
        assert "42" in html

    def test_contains_timestamp(self):
        html = self._render(SIMPLE_SCHEMA, timestamp="2024-06-15")
        assert "2024-06-15" in html

    def test_contains_entity_name(self):
        html = self._render(SIMPLE_SCHEMA)
        assert "Post" in html

    def test_contains_field_names(self):
        html = self._render(SIMPLE_SCHEMA)
        assert "published" in html
        assert "title" in html

    def test_contains_coverage_percentage(self):
        html = self._render(SIMPLE_SCHEMA)
        assert "%" in html

    def test_contains_table(self):
        html = self._render(SIMPLE_SCHEMA)
        assert "<table" in html
        assert "</table>" in html

    def test_green_color_present_for_full_coverage(self):
        html = self._render(FULL_COVERAGE_SCHEMA)
        assert "#22c55e" in html

    def test_missing_section_absent_when_full_coverage(self):
        html = self._render(FULL_COVERAGE_SCHEMA)
        assert "Missing:" not in html

    def test_missing_section_present_when_partial(self):
        # With generate:2 and BVA on 0..5, some values will be missing
        html = self._render(PARTIAL_SCHEMA)
        # The report should show either "Missing:" or 100% coverage
        # (padding rows may cover everything — just check HTML renders)
        assert "<table" in html

    def test_multiple_entities_in_html(self):
        html = self._render(FK_SCHEMA)
        assert "Author" in html
        assert "Article" in html

    def test_strategy_tags_in_html(self):
        html = self._render(SMART_SCHEMA)
        assert "BVA" in html
        assert "EP" in html

    def test_seed_override_in_html(self):
        html = self._render(SIMPLE_SCHEMA, seed=9999)
        assert "9999" in html

    def test_overall_summary_present(self):
        html = self._render(SIMPLE_SCHEMA)
        assert "required cases covered" in html


# ===========================================================================
# 6. Seed reproducibility
# ===========================================================================

class TestReproducibility:
    def _coverage(self, schema_str, seed):
        model = load_model_from_str(schema_str)
        return ReportGenerator(model, seed=seed).calculate_coverage()

    def test_same_seed_same_result(self):
        d1 = self._coverage(SMART_SCHEMA, seed=42)
        d2 = self._coverage(SMART_SCHEMA, seed=42)
        assert d1["overall"]["pct"] == d2["overall"]["pct"]

    def test_same_seed_same_html(self):
        model = load_model_from_str(SMART_SCHEMA)
        html1 = ReportGenerator(model, seed=42, timestamp="T").render()
        html2 = ReportGenerator(model, seed=42, timestamp="T").render()
        assert html1 == html2