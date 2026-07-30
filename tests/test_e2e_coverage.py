import pytest
from testdatagen.generators.report_generator import ReportGenerator
from grammar_loader import load_model
from testdatagen.cli import main
import os
import shutil
import re

FILES = [
    {
        "file_name": "ecommerce", 
        "schema_name": "Ecommerce",
        "objects": ["User", "Product", "Order"],
        "seed": 123,
        "relationships": []
    },
    {
        "file_name": "minimal", 
        "schema_name": "Blog",
        "objects": ["Post", "User"],
        "seed": 999,
        "relationships": []
    },
    {
        "file_name": "edge_cases", 
        "schema_name": "BankingSystem",
        "objects": ["Customer"],
        "seed": 2026,
        "relationships": []
    },
    {
        "file_name": "complex_refs", 
        "schema_name": "UniversitySystem",
        "objects": ["Professor", "Course", "Student", "Exam"],
        "seed": 12345,
        "relationships": []
    },
    {
        "file_name": "relationships",
        "schema_name": "ProjectManagement",
        "objects": ["Developer", "Project", "Task"],
        "seed": 777,
        "relationships": ["AssignedTo", "Contributes"]
    }
]

def _calculate_helper(file_name, seed, objects, expected_relationships):
    model = load_model(f'tests/fixtures/{file_name}.tdata')
    
    generator = ReportGenerator(model, seed=seed)
    
    report_data = generator.calculate_coverage()
    
    assert "overall" in report_data, "Key 'overall' is missing in report data"
    assert "entities" in report_data, "Key 'entities' is missing in report data"
    assert "relationships" in report_data, "Key 'relationships' is missing in report data"
    
    pct = report_data["overall"]["pct"]
    assert 0 <= pct <= 100, f"Coverage percentage {pct} is out of bounds (0-100)"
    
    # Entity assertions
    entity_names = [e["name"] for e in report_data["entities"]]
    for entity in objects:
        assert entity in entity_names, f"Entity '{entity}' not found in report entities"
    assert len(objects) == len(entity_names), "Number of entities does not match expected count"

    # Relationship assertions
    rel_names = [r["name"] for r in report_data["relationships"]]
    for rel in expected_relationships:
        assert rel in rel_names, f"Relationship '{rel}' was not found in the report!"
    assert len(expected_relationships) == len(rel_names), "Number of generated relationships does not match the expected count!"

def test_coverage_calculation_logic():
    for example in FILES:
        _calculate_helper(
            example["file_name"], 
            example["seed"],
            example["objects"],
            example["relationships"]
        )

def _file_helper(runner, schema_dir, file_name, schema_name, expected_relationships):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')

    result = runner.invoke(main, [
        'generate', 
        schema_path, 
        '--output', str(schema_dir), 
        '--format', 'report' 
    ])
    
    assert result.exit_code == 0, f"CLI error: {result.output}"
    html_report_path = schema_dir / f"{schema_name}.html"
    assert html_report_path.exists(), "HTML report file was not created!"

    with open(html_report_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    if expected_relationships:
        assert "Relationships" in html_content, "The 'Relationships' section is missing from the HTML report even though the schema defines relationships!"
        for rel in expected_relationships:
            assert rel in html_content, f"Relationship name '{rel}' is not displayed in the HTML report!"
    else:
        assert "Relationships" not in html_content, "The 'Relationships' section is displayed even though the schema has no defined relationships!"

def test_coverage_file_generation(runner, schema_dir):
    for example in FILES:
        _file_helper(
            runner,
            schema_dir,
            example["file_name"], 
            example["schema_name"],
            example["relationships"]
        )

def _normalize_report(content):
    timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
    normalized = re.sub(timestamp_pattern, '[TIMESTAMP]', content)
    return normalized

def _seed_reproducibility(runner, schema_dir, file_name, seed, schema_name):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')
    
    runner.invoke(main, ['generate', schema_path, '--output', str(schema_dir), '--format', 'report', '--seed', seed])
    with open(os.path.join(schema_dir, f'{schema_name}.html'), 'r', encoding='utf-8') as f:
        run1 = f.read()
        
    shutil.rmtree(schema_dir)
    os.makedirs(schema_dir)
    
    runner.invoke(main, ['generate', schema_path, '--output', str(schema_dir), '--format', 'report', '--seed', seed])
    with open(os.path.join(schema_dir, f'{schema_name}.html'), 'r', encoding='utf-8') as f:
        run2 = f.read()
        
    assert _normalize_report(run1) == _normalize_report(run2), "Report files differ between runs despite using the same seed (timestamps normalized)!"

def test_report_seed_reproducibility(runner, schema_dir):
    for example in FILES:
        _seed_reproducibility(
            runner,
            schema_dir,
            example["file_name"],
            example["seed"],  
            example["schema_name"]
        )