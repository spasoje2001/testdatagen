import pytest
from click.testing import CliRunner
from testdatagen.cli import main

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def schema_dir(tmp_path):
    return tmp_path