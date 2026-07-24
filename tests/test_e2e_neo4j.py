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

def _generate_neo4j_helper(runner, schema_dir, file_name, schema_name, objects):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')
    
    result = runner.invoke(main, [
        'generate', schema_path, 
        '--output', str(schema_dir), 
        '--format', 'neo4j'
    ])
    
    assert result.exit_code == 0, f"CLI error: {result.output}"
    
    cypher_file_path = os.path.join(schema_dir, f'{schema_name}.cypher')
    assert os.path.exists(cypher_file_path), f"Cypher file {schema_name}.cypher was not created."
    
    content = open(cypher_file_path, 'r', encoding='utf-8').read()
    
    assert schema_name in content
    
    for entity_name, expected_count in objects:
        create_pattern = f"(:{entity_name}"
        actual_count = content.count(create_pattern)
        assert actual_count == expected_count, f"Expected {expected_count} nodes for {entity_name}, but found {actual_count} in Cypher script."

def test_generate_neo4j_structure(runner, schema_dir):
    for example in FILES:
        _generate_neo4j_helper(
            runner, 
            schema_dir, 
            example["file_name"], 
            example["schema_name"], 
            example["objects"]
        )

def _seed_reproducibility_neo4j(runner, schema_dir, file_name, seed, schema_name):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')
    
    runner.invoke(main, ['generate', schema_path, '--output', str(schema_dir), '--format', 'neo4j', '--seed', seed])
    cypher_path = os.path.join(schema_dir, f'{schema_name}.cypher')
    
    with open(cypher_path, 'r', encoding='utf-8') as f:
        run1 = f.read()
        
    shutil.rmtree(schema_dir)
    os.makedirs(schema_dir)
    
    runner.invoke(main, ['generate', schema_path, '--output', str(schema_dir), '--format', 'neo4j', '--seed', seed])
    with open(cypher_path, 'r', encoding='utf-8') as f:
        run2 = f.read()

    run1_lines = [
        line for line in run1.splitlines() 
        if "generated" not in line.lower() and "date" not in line.lower()
    ]
    run2_lines = [
        line for line in run2.splitlines() 
        if "generated" not in line.lower() and "date" not in line.lower()
    ]
    
    assert run1_lines == run2_lines, "Cypher files generated with the same seed are different"

def test_neo4j_seed_reproducibility(runner, schema_dir):
    for example in FILES:
        _seed_reproducibility_neo4j(
            runner, 
            schema_dir, 
            example["file_name"], 
            example["seed"], 
            example["schema_name"]
        )
