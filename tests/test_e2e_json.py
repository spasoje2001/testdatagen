import json
import pytest
from testdatagen.cli import main
import os
import shutil

FILES = [
     {
        "file_name": "ecommerce", 
        "schema_name": "Ecommerce",
        "objects": [["User", 50], ["Product", 100], ["Order", 200]],
        "seed": "123"
    },
    {
        "file_name": "minimal", 
        "schema_name": "Blog",
        "objects": [["Post", 15], ["User", 10]],
        "seed": "999"
    },
    {
        "file_name": "edge_cases", 
        "schema_name": "BankingSystem",
        "objects": [["Customer", 50]],
        "seed": "2026"
    },
    {
        "file_name": "complex_refs", 
        "schema_name": "UniversitySystem",
        "objects": [["Professor", 12], ["Course", 20], ["Student", 40], ["Exam", 120]],
        "seed": "12345"
    }
]

def _generate_helper(runner, schema_dir, file_name, schema_name, objects):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')
    
    result = runner.invoke(main, [
        'generate', schema_path, 
        '--output', str(schema_dir), 
        '--format', 'json'
    ])
    
    assert result.exit_code == 0, f"CLI error: {result.output}"
    
    with open(os.path.join(schema_dir, f'{schema_name}.json'), 'r') as f:
        data = json.load(f)
    
    assert "metadata" in data
    assert data["metadata"]["schema"] == schema_name
    
    assert "entities" in data
    for entity in objects:
        assert entity[0] in data["entities"]
        assert len(data["entities"][entity[0]]) == entity[1]

def test_generate_json_structure(runner, schema_dir):
    for example in FILES:
        _generate_helper(
            runner, 
            schema_dir, 
            example["file_name"], 
            example["schema_name"], 
            example["objects"]
        )

def _seed_reproducibility(runner, schema_dir, file_name, seed, schema_name):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')
    
    runner.invoke(main, ['generate', schema_path, '--output', str(schema_dir), '--format', 'json', '--seed', seed])
    with open(os.path.join(schema_dir, f'{schema_name}.json'), 'r') as f:
        run1 = json.load(f)
        
    shutil.rmtree(schema_dir)
    os.makedirs(schema_dir)
    
    runner.invoke(main, ['generate', schema_path, '--output', str(schema_dir), '--format', 'json', '--seed', seed])
    with open(os.path.join(schema_dir, f'{schema_name}.json'), 'r') as f:
        run2 = json.load(f)
        
    del run1["metadata"]["generated_at"]
    del run2["metadata"]["generated_at"]
    
    assert run1 == run2, "JSON files are different"

def test_json_seed_reproducibility(runner, schema_dir):
    for example in FILES:
        _seed_reproducibility(
            runner, 
            schema_dir, 
            example["file_name"], 
            example["seed"], 
            example["schema_name"]
        )