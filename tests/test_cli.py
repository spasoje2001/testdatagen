import os
import pytest
from click.testing import CliRunner
from testdatagen.cli import main

@pytest.fixture
def runner():
    return CliRunner()

# ==========================================
# 1. Unit tests for argument parsing
# ==========================================
def test_cli_version(runner):
    result = runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert "version" in result.output.lower()

def test_invalid_format_option(runner, tmp_path):
    dummy_file = tmp_path / "schema.tdg"
    dummy_file.write_text('schema TestSchema { entity Test { fields { t: string } } }')
    
    result = runner.invoke(main, ['generate', str(dummy_file), '-f', 'invalid_fmt'])
    assert result.exit_code == 2
    assert "unsupported formats" in result.output.lower()

# ==========================================
# 2. Integration tests for validate command
# ==========================================
def test_validate_success(runner, tmp_path):
    schema_file = tmp_path / "valid.tdg"
    schema_file.write_text('schema TestSchema { entity Test { fields { t: string } } }')

    result = runner.invoke(main, ['validate', str(schema_file)])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()

def test_validate_stdin(runner):
    valid_schema_content = 'schema TestSchema { entity Test { fields { t: string } } }'
    
    result = runner.invoke(main, ['validate', '-'], input=valid_schema_content)
    assert result.exit_code == 0

# ==========================================
# 3. Integration tests for generate command
# ==========================================
def test_generate_success(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text('schema TestSchema { entity Test { fields { t: string } } }')
    output_dir = tmp_path / "output"

    result = runner.invoke(main, ['generate', str(schema_file), '--output', str(output_dir), '-f', 'sql'])
    assert result.exit_code == 0

# ==========================================
# 4. Tests for error handling & exit codes
# ==========================================
def test_semantic_error_handling(runner, tmp_path):
    schema_file = tmp_path / "invalid_range.tdg"
    schema_file.write_text('schema Test { entity T { fields { t: number { range 100 .. 10 } } } }')
    
    result = runner.invoke(main, ['validate', str(schema_file)])
    assert result.exit_code == 1
    assert "semantic error" in result.output.lower()

def test_syntax_error_handling(runner, tmp_path):
    schema_file = tmp_path / "bad_syntax.tdg"
    schema_file.write_text('schema BadSchema entity Test fields t: string')
    
    result = runner.invoke(main, ['validate', str(schema_file)])
    assert result.exit_code == 1
    assert "syntax error" in result.output.lower()
