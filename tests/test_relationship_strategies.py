"""
Unit tests for relationship strategies (one-to-one, one-to-many, many-to-one, many-to-many)
located in testdatagen generators.

Run with:
    pytest tests/test_relationship_strategies.py -v
"""

import pytest
from types import SimpleNamespace

from testdatagen.strategies.relationships import (
    _one_to_one,
    _one_to_many,
    _many_to_one,
    _many_to_many,
)


@pytest.fixture
def mock_relationship():
    return SimpleNamespace(
        name="BelongsTo",
        from_=SimpleNamespace(name="User"),
        to=SimpleNamespace(name="Organization"),
    )


@pytest.fixture
def sample_rows():
    from_rows = [{"id": f"u-{i}"} for i in range(5)]
    to_rows = [{"id": f"org-{j}"} for j in range(3)]
    return from_rows, to_rows


# ===========================================================================
# 1. Test _one_to_one
# ===========================================================================

class TestOneToOneStrategy:
    def test_one_to_one_generates_correct_count(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        results = list(_one_to_one(mock_relationship, from_rows, to_rows))
        
        assert len(results) == 3

    def test_one_to_one_respects_generate_limit(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        results = list(_one_to_one(mock_relationship, from_rows, to_rows, generate=2))
        
        assert len(results) == 2

    def test_one_to_one_structure_and_properties(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        prop_rows = [{"role": "admin"}, {"role": "member"}]
        results = list(_one_to_one(mock_relationship, from_rows, to_rows, prop_rows=prop_rows))
        
        assert results[0]["from_id"] == "u-0"
        assert results[0]["to_id"] == "org-0"
        assert results[0]["type"] == "BELONGSTO"
        assert results[0]["properties"] == {"role": "admin"}
        assert results[1]["properties"] == {"role": "member"}
        assert results[2]["properties"] == {}


# ===========================================================================
# 2. Test _one_to_many
# ===========================================================================

class TestOneToManyStrategy:
    def test_one_to_many_reproducibility_with_seed(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        res1 = list(_one_to_many(mock_relationship, from_rows, to_rows, seed=42, generate=10))
        res2 = list(_one_to_many(mock_relationship, from_rows, to_rows, seed=42, generate=10))
        
        assert res1 == res2

    def test_one_to_many_respects_generate_limit(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        results = list(_one_to_many(mock_relationship, from_rows, to_rows, generate=4, seed=123))
        
        assert len(results) == 4

    def test_one_to_many_degree_bounds(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        results = list(_one_to_many(mock_relationship, from_rows, to_rows, min_degree=1, max_degree=2, seed=1))
        
        for r in results:
            assert r["type"] == "BELONGSTO"
            assert r["from_label"] == "User"
            assert r["to_label"] == "Organization"


# ===========================================================================
# 3. Test _many_to_one
# ===========================================================================

class TestManyToOneStrategy:
    def test_many_to_one_generates_one_per_source(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        results = list(_many_to_one(mock_relationship, from_rows, to_rows, seed=10))
        
        # Svaki entitet iz from_rows mora imati bar jednu vezu (ukupno 5)
        assert len(results) == len(from_rows)
        for i, r in enumerate(results):
            assert r["from_id"] == from_rows[i]["id"]
            assert r["to_id"] in [t["id"] for t in to_rows]

    def test_many_to_one_respects_generate_limit(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        results = list(_many_to_one(mock_relationship, from_rows, to_rows, generate=2, seed=5))
        
        assert len(results) == 2

    def test_many_to_one_properties_mapping(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        prop_rows = [{"since": 2021}, {"since": 2022}]
        results = list(_many_to_one(mock_relationship, from_rows, to_rows, prop_rows=prop_rows, seed=1))
        
        assert results[0]["properties"] == {"since": 2021}
        assert results[1]["properties"] == {"since": 2022}
        assert results[2]["properties"] == {}


# ===========================================================================
# 4. Test _many_to_many
# ===========================================================================

class TestManyToManyStrategy:
    def test_many_to_many_reproducibility_with_seed(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        res1 = list(_many_to_many(mock_relationship, from_rows, to_rows, seed=99, generate=8))
        res2 = list(_many_to_many(mock_relationship, from_rows, to_rows, seed=99, generate=8))
        
        assert res1 == res2

    def test_many_to_many_respects_generate_limit(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        results = list(_many_to_many(mock_relationship, from_rows, to_rows, generate=6, seed=77))
        
        assert len(results) == 6

    def test_many_to_many_fields_structure(self, mock_relationship, sample_rows):
        from_rows, to_rows = sample_rows
        results = list(_many_to_many(mock_relationship, from_rows, to_rows, min_degree=1, max_degree=2, seed=3))
        
        for r in results:
            assert "from_label" in r
            assert "from_id" in r
            assert "to_label" in r
            assert "to_id" in r
            assert r["type"] == "BELONGSTO"
            assert isinstance(r["properties"], dict)
