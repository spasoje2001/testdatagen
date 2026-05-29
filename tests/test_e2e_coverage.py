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
        "seed": 123
    },
    {
        "file_name": "minimal", 
        "schema_name": "Blog",
        "objects": ["Post", "User"],
        "seed": 999
    },
    {
        "file_name": "edge_cases", 
        "schema_name": "BankingSystem",
        "objects": ["Customer"],
        "seed": 2026
    },
    {
        "file_name": "complex_refs", 
        "schema_name": "UniversitySystem",
        "objects": ["Professor", "Course", "Student", "Exam"],
        "seed": 12345
    }
]

def _calculate_helper(file_name, seed, objects):
    model = load_model(f'tests/fixtures/{file_name}.tdata')
    
    generator = ReportGenerator(model, seed=seed)
    
    report_data = generator.calculate_coverage()
    
    assert "overall" in report_data
    assert "entities" in report_data
    
    pct = report_data["overall"]["pct"]
    assert 0 <= pct <= 100
    
    entity_names = [e["name"] for e in report_data["entities"]]
    for entity in objects:
        assert entity in entity_names
        assert entity in entity_names
    assert len(objects) == len(entity_names)

def test_coverage_calculation_logic():
    for example in FILES:
        _calculate_helper(
            example["file_name"], 
            example["seed"],
            example["objects"]
        )

def _file_helper(runner, schema_dir, file_name, schema_name):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')

    result = runner.invoke(main, [
        'generate', 
        schema_path, 
        '--output', str(schema_dir), 
        '--format', 'report' 
    ])
    
    assert result.exit_code == 0, f"CLI error: {result.output}"
    assert (schema_dir / f"{schema_name}.html").exists(), "HTML report is not created!"

def test_coverage_file_generation(runner, schema_dir):
    for example in FILES:
        _file_helper(
            runner,
            schema_dir,
            example["file_name"], 
            example["schema_name"]
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
        
    assert _normalize_report(run1) == _normalize_report(run2), "REPORT files are different after we delete lines with time!"

def test_report_seed_reproducibility(runner, schema_dir):
    for example in FILES:
        _seed_reproducibility(
            runner,
            schema_dir,
            example["file_name"],
            example["seed"],  
            example["schema_name"]
        )
