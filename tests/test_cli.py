import os
import pytest
from click.testing import CliRunner

from testdatagen.cli import main, SUPPORTED_FORMATS


@pytest.fixture
def runner():
    return CliRunner()


# ==========================================
# 1. Unit tests for CLI & argument parsing
# ==========================================

def test_cli_version(runner):
    result = runner.invoke(main, ["--version"])

    assert result.exit_code == 0
    assert "version" in result.output.lower()


def test_supported_formats():
    assert {
        "sql",
        "json",
        "csv",
        "yaml",
        "report",
    }.issubset(SUPPORTED_FORMATS)


def test_invalid_format_option(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        "schema TestSchema { entity Test { fields { t: string } } }"
    )

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "-f",
            "invalid_format",
        ],
    )

    assert result.exit_code == 2
    assert "unsupported formats" in result.output.lower()


# ==========================================
# 2. Integration tests for validate command
# ==========================================

def test_validate_success(runner, tmp_path):
    schema_file = tmp_path / "valid.tdg"
    schema_file.write_text(
        "schema TestSchema { entity Test { fields { t: string } } }"
    )

    result = runner.invoke(main, ["validate", str(schema_file)])

    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_validate_stdin(runner):
    schema = "schema TestSchema { entity Test { fields { t: string } } }"

    result = runner.invoke(
        main,
        ["validate", "-"],
        input=schema,
    )

    assert result.exit_code == 0


# ==========================================
# 3. Integration tests for generate command
# ==========================================

def test_generate_sql_format(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        "schema TestSchema { entity Test { fields { t: string } } }"
    )

    output_dir = tmp_path / "sql"

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "sql",
        ],
    )

    assert result.exit_code == 0
    assert len(os.listdir(output_dir)) > 0


def test_generate_json_format(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        "schema TestSchema { entity Test { fields { t: string } } }"
    )

    output_dir = tmp_path / "json"

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "TestSchema.json").exists()


def test_generate_report_format(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        "schema TestSchema { entity Test { fields { t: string } } }"
    )

    output_dir = tmp_path / "report"

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "report",
        ],
    )

    assert result.exit_code == 0
    assert len(os.listdir(output_dir)) > 0


def test_generate_csv_format(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        """
        schema TestSchema {
            entity Test {
                fields {
                    id: uuid
                    name: string
                }
            }
        }
        """
    )

    output_dir = tmp_path / "csv"

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "csv",
        ],
    )

    assert result.exit_code == 0

    csv_dir = output_dir / "TestSchema"

    assert csv_dir.exists()
    assert (csv_dir / "Test.csv").exists()
    assert (csv_dir / "generation_details.txt").exists()


def test_generate_yaml_format(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        """
        schema TestSchema {
            entity Test {
                fields {
                    id: uuid
                    name: string
                }
            }
        }
        """
    )

    output_dir = tmp_path / "yaml"

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "yaml",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "TestSchema.yaml").exists()


def test_generation_details_created(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        """
        schema TestSchema {
            entity Test {
                fields {
                    id: uuid
                    name: string
                }
            }
        }
        """
    )

    output_dir = tmp_path / "csv"

    runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "csv",
        ],
    )

    details = (
        output_dir
        / "TestSchema"
        / "generation_details.txt"
    )

    assert details.exists()

    content = details.read_text()

    assert "Schema:" in content
    assert "Format: CSV" in content
    assert "Generated at:" in content
    assert "Total records:" in content


def test_generate_multiple_formats(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        """
        schema TestSchema {
            entity Test {
                fields {
                    id: uuid
                    name: string
                }
            }
        }
        """
    )

    output_dir = tmp_path / "multi"

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "sql,json,csv,yaml",
        ],
    )

    assert result.exit_code == 0

    assert (output_dir / "TestSchema.sql").exists()
    assert (output_dir / "TestSchema.json").exists()
    assert (output_dir / "TestSchema").exists()
    assert (output_dir / "TestSchema.yaml").exists()


# ==========================================
# 4. Tests for CLI options
# ==========================================

def test_generate_with_seed_override(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        """
        schema TestSchema {
            seed: 111

            entity Test {
                fields {
                    value: number { range 1..10 }
                }
            }
        }
        """
    )

    output_dir = tmp_path / "seed"

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "json",
            "-s",
            "999",
        ],
    )

    assert result.exit_code == 0


def test_generate_overwrite_sql(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        "schema Test { entity T { fields { t: string } } }"
    )

    output_dir = tmp_path / "sql"

    runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "sql",
        ],
    )

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "sql",
        ],
    )

    assert result.exit_code != 0

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "sql",
            "--overwrite",
        ],
    )

    assert result.exit_code == 0


def test_generate_overwrite_csv(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        """
        schema TestSchema {
            entity Test {
                fields {
                    id: uuid
                }
            }
        }
        """
    )

    output_dir = tmp_path / "csv"

    runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "csv",
        ],
    )

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "csv",
        ],
    )

    assert result.exit_code != 0

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "csv",
            "--overwrite",
        ],
    )

    assert result.exit_code == 0


def test_generate_overwrite_yaml(runner, tmp_path):
    schema_file = tmp_path / "schema.tdg"
    schema_file.write_text(
        """
        schema TestSchema {
            entity Test {
                fields {
                    id: uuid
                }
            }
        }
        """
    )

    output_dir = tmp_path / "yaml"

    runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "yaml",
        ],
    )

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "yaml",
        ],
    )

    assert result.exit_code != 0

    result = runner.invoke(
        main,
        [
            "generate",
            str(schema_file),
            "--output",
            str(output_dir),
            "-f",
            "yaml",
            "--overwrite",
        ],
    )

    assert result.exit_code == 0


# ==========================================
# 5. Error handling & exit codes
# ==========================================

def test_semantic_error_handling(runner, tmp_path):
    schema_file = tmp_path / "semantic.tdg"

    schema_file.write_text(
        """
        schema Test {
            entity T {
                fields {
                    n: number {
                        range 100 .. 10
                    }
                }
            }
        }
        """
    )

    result = runner.invoke(
        main,
        ["validate", str(schema_file)],
    )

    assert result.exit_code == 1
    assert "semantic error" in result.output.lower()


def test_syntax_error_handling(runner, tmp_path):
    schema_file = tmp_path / "syntax.tdg"

    schema_file.write_text(
        "schema Bad entity Test fields"
    )

    result = runner.invoke(
        main,
        ["validate", str(schema_file)],
    )

    assert result.exit_code == 1
    assert "syntax error" in result.output.lower()


def test_generate_from_stdin(runner, tmp_path):
    schema = """
    schema TestSchema {
        entity Test {
            fields {
                id: uuid
            }
        }
    }
    """

    output_dir = tmp_path / "stdin"

    result = runner.invoke(
        main,
        [
            "generate",
            "-",
            "--output",
            str(output_dir),
            "-f",
            "csv",
        ],
        input=schema,
    )

    assert result.exit_code == 0
    assert (output_dir / "TestSchema").exists()