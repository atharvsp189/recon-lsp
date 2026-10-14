import os
import sys
import tempfile
import pytest
from pathlib import Path
from typer.testing import CliRunner


@pytest.fixture
def runner():
    """Typer CLI runner for testing command invocations."""
    return CliRunner()


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a clean temporary directory as a Path object."""
    return tmp_path


@pytest.fixture
def sample_code():
    """Sample Python code for testing symbol search and context."""
    return (
        "import os\n"
        "import sys\n"
        "\n"
        "def calculate_sum(a, b):\n"
        "    result = a + b\n"
        "    return result\n"
        "\n"
        "class Calculator:\n"
        "    def __init__(self, initial=0):\n"
        "        self.value = initial\n"
        "\n"
        "    def add(self, amount):\n"
        "        self.value += amount\n"
        "        return self.value\n"
    )


@pytest.fixture
def temp_repo(tmp_path, sample_code):
    """Temporary repository containing sample source files and structure."""
    repo = tmp_path / "test_repo"
    repo.mkdir(parents=True, exist_ok=True)

    src_file = repo / "main.py"
    src_file.write_text(sample_code, encoding="utf-8")

    sub_dir = repo / "pkg"
    sub_dir.mkdir(parents=True, exist_ok=True)
    sub_file = sub_dir / "helper.py"
    sub_file.write_text("def helper_fn():\n    pass\n", encoding="utf-8")

    return repo


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Isolate config and daemon directories to temporary locations."""
    home_dir = tmp_path / "fake_home"
    home_dir.mkdir(parents=True, exist_ok=True)

    config_home = tmp_path / "fake_config"
    config_home.mkdir(parents=True, exist_ok=True)

    runtime_dir = tmp_path / "fake_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    local_app_data = tmp_path / "fake_localappdata"
    local_app_data.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    return {
        "home": home_dir,
        "config": config_home,
        "runtime": runtime_dir,
        "localappdata": local_app_data,
    }
