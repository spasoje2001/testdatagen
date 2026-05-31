import os
import pytest
from testdatagen.cli import main
from click.testing import CliRunner
import shutil

FILES = [
    {
        "file_name": "minimal", 
        "schema_name": "Blog",
        "seed": "123",
        "table_names": ["posts", "users"]
    },
    {
        "file_name": "edge_cases", 
        "schema_name": "BankingSystem",
        "seed": "999",
        "table_names": ["customers"]
    },
    {
        "file_name": "complex_refs", 
        "schema_name": "UniversitySystem",
        "seed": "2026",
        "table_names": ["professors", "courses", "students", "exams"]
    },
    {
        "file_name": "ecommerce", 
        "schema_name": "Ecommerce",
        "seed": "12345",
        "table_names": ["users", "products", "orders"]
    }
]

@pytest.fixture
def runner():
    return CliRunner()

def _generate_helper(runner, schema_dir, file_name, schema_name, seed, table_names):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')
    result = runner.invoke(main, [
        'generate', schema_path, 
        '--output', str(schema_dir), 
        '--format', 'sql',
        '--seed', seed
    ])

    assert result.exit_code == 0,f"CLI is exit with code {result.exit_code}. Error: {result.output}"
    assert "Success" in result.output
    output_files = os.listdir(schema_dir)
    assert f'{schema_name}.sql' in output_files

    with open(os.path.join(schema_dir, f'{schema_name}.sql'), 'r') as f:
        content = f.read()
        assert f"-- Schema: {schema_name}" in content
        assert f"-- Seed: {seed}" in content
        for name in table_names:
            assert f"INSERT INTO {name}" in content
        assert "VALUES" in content
        assert len(content) > 500
        assert content.strip().endswith(";")

def test_generate_sql_minimal(runner, schema_dir):
    for example in FILES:
        _generate_helper(
            runner, 
            schema_dir, 
            example["file_name"], 
            example["schema_name"], 
            example["seed"], 
            example["table_names"]
        )

def _strip_timestamp(content):
    return "\n".join([line for line in content.splitlines() if "-- generated at:" not in line.lower()])

def _seed_reproducibility(runner, schema_dir, file_name, seed, schema_name):
    schema_path = os.path.join(os.path.dirname(__file__), 'fixtures', f'{file_name}.tdata')
    
    runner.invoke(main, ['generate', schema_path, '--output', str(schema_dir), '--format', 'sql', '--seed', seed])
    with open(os.path.join(schema_dir, f'{schema_name}.sql'), 'r') as f:
        run1 = f.read()
        
    shutil.rmtree(schema_dir)
    os.makedirs(schema_dir)
    
    runner.invoke(main, ['generate', schema_path, '--output', str(schema_dir), '--format', 'sql', '--seed', seed])
    with open(os.path.join(schema_dir, f'{schema_name}.sql'), 'r') as f:
        run2 = f.read()
    
    assert _strip_timestamp(run1) == _strip_timestamp(run2), "SQL files are different after we delete lines with time"

def test_seed_reproducibility(runner, schema_dir):
    for example in FILES:
        _seed_reproducibility(
            runner, 
            schema_dir, 
            example["file_name"],
            example["seed"],  
            example["schema_name"]
        )
