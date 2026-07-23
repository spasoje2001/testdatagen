import csv
import os
import shutil

from testdatagen.cli import main


FILES = [
    {
        "file_name": "ecommerce",
        "schema_name": "Ecommerce",
        "objects": [["User", 50], ["Product", 100], ["Order", 200]],
        "seed": "123",
    },
    {
        "file_name": "minimal",
        "schema_name": "Blog",
        "objects": [["Post", 15], ["User", 10]],
        "seed": "999",
    },
    {
        "file_name": "edge_cases",
        "schema_name": "BankingSystem",
        "objects": [["Customer", 50]],
        "seed": "2026",
    },
    {
        "file_name": "complex_refs",
        "schema_name": "UniversitySystem",
        "objects": [
            ["Professor", 12],
            ["Course", 20],
            ["Student", 40],
            ["Exam", 120],
        ],
        "seed": "12345",
    },
]


# ==========================================================
# Helpers
# ==========================================================

def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _generate_helper(runner, schema_dir, file_name, schema_name, objects):
    schema_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        f"{file_name}.tdata",
    )

    result = runner.invoke(
        main,
        [
            "generate",
            schema_path,
            "--output",
            str(schema_dir),
            "--format",
            "csv",
        ],
    )

    assert result.exit_code == 0, f"CLI error:\n{result.output}"

    output_folder = os.path.join(schema_dir, schema_name)

    assert os.path.isdir(output_folder)

    metadata_path = os.path.join(output_folder, "generation_details.txt")
    assert os.path.exists(metadata_path)

    with open(metadata_path, encoding="utf-8") as f:
        metadata = f.read()

    assert f"Schema: {schema_name}" in metadata
    assert "Format: CSV" in metadata

    for entity_name, expected_rows in objects:

        csv_path = os.path.join(output_folder, f"{entity_name}.csv")

        assert os.path.exists(csv_path)

        rows = _read_csv(csv_path)

        assert len(rows) == expected_rows

        assert len(rows) > 0
        assert len(rows[0].keys()) > 0


# ==========================================================
# Structure
# ==========================================================

def test_generate_csv_structure(runner, schema_dir):
    for example in FILES:
        _generate_helper(
            runner,
            schema_dir,
            example["file_name"],
            example["schema_name"],
            example["objects"],
        )


# ==========================================================
# Seed reproducibility
# ==========================================================

def _seed_reproducibility(
    runner,
    schema_dir,
    file_name,
    seed,
    schema_name,
):
    schema_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        f"{file_name}.tdata",
    )

    runner.invoke(
        main,
        [
            "generate",
            schema_path,
            "--output",
            str(schema_dir),
            "--format",
            "csv",
            "--seed",
            seed,
        ],
    )

    output_folder = os.path.join(schema_dir, schema_name)

    run1 = {}

    for file in os.listdir(output_folder):
        if file.endswith(".csv"):
            run1[file] = _read_csv(os.path.join(output_folder, file))

    shutil.rmtree(schema_dir)
    os.makedirs(schema_dir)

    runner.invoke(
        main,
        [
            "generate",
            schema_path,
            "--output",
            str(schema_dir),
            "--format",
            "csv",
            "--seed",
            seed,
        ],
    )

    output_folder = os.path.join(schema_dir, schema_name)

    run2 = {}

    for file in os.listdir(output_folder):
        if file.endswith(".csv"):
            run2[file] = _read_csv(os.path.join(output_folder, file))

    assert run1 == run2, "CSV output differs for identical seed"


def test_csv_seed_reproducibility(runner, schema_dir):
    for example in FILES:
        _seed_reproducibility(
            runner,
            schema_dir,
            example["file_name"],
            example["seed"],
            example["schema_name"],
        )


# ==========================================================
# Metadata file
# ==========================================================

def test_generation_details_file(runner, schema_dir):
    example = FILES[0]

    schema_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        f"{example['file_name']}.tdata",
    )

    result = runner.invoke(
        main,
        [
            "generate",
            schema_path,
            "--output",
            str(schema_dir),
            "--format",
            "csv",
        ],
    )

    assert result.exit_code == 0

    metadata_path = os.path.join(
        schema_dir,
        example["schema_name"],
        "generation_details.txt",
    )

    assert os.path.exists(metadata_path)

    with open(metadata_path, encoding="utf-8") as f:
        content = f.read()

    assert "TestDataGen CSV Generation" in content
    assert f"Schema: {example['schema_name']}" in content
    assert "Generated at:" in content
    assert "Format: CSV" in content
    assert "Entities:" in content
    assert "Total records:" in content


# ==========================================================
# CSV headers
# ==========================================================

def test_csv_contains_headers(runner, schema_dir):
    example = FILES[0]

    schema_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        f"{example['file_name']}.tdata",
    )

    runner.invoke(
        main,
        [
            "generate",
            schema_path,
            "--output",
            str(schema_dir),
            "--format",
            "csv",
        ],
    )

    csv_path = os.path.join(
        schema_dir,
        example["schema_name"],
        "User.csv",
    )

    rows = _read_csv(csv_path)

    assert len(rows) > 0

    headers = list(rows[0].keys())

    assert len(headers) > 0
    assert "id" in headers


def test_array_refs_are_semicolon_separated(runner, schema_dir):
    schema_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "complex_refs.tdata",
    )

    result = runner.invoke(
        main,
        [
            "generate",
            schema_path,
            "--output",
            str(schema_dir),
            "--format",
            "csv",
        ],
    )

    assert result.exit_code == 0

    student_csv = os.path.join(
        schema_dir,
        "UniversitySystem",
        "Student.csv",
    )

    rows = _read_csv(student_csv)

    assert len(rows) == 40

    found_non_empty = False

    for row in rows:
        value = row["enrolledCourses"]

        if value:
            found_non_empty = True

            ids = value.split(";")

            assert len(ids) >= 1
            assert all(i != "" for i in ids)

    assert found_non_empty

    for row in rows:
        value = row["enrolledCourses"]

        if value:
            ids = value.split(";")

            assert 1 <= len(ids) <= 8
            assert all(i != "" for i in ids)
