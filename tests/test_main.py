import json
from unittest.mock import MagicMock
from pathlib import Path
import pytest
from typer.testing import CliRunner

from recon.main import app, version_callback


def test_version_flag(runner):
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert "Recon LSP Version:" in res.output


def test_version_callback_package_not_found(monkeypatch):
    import importlib.metadata

    def fake_version(pkg):
        raise importlib.metadata.PackageNotFoundError()

    monkeypatch.setattr(importlib.metadata, "version", fake_version)
    runner = CliRunner()
    res = runner.invoke(app, ["-v"])
    assert res.exit_code == 0
    assert "unknown" in res.output


def test_agent_skill_packaged_data(runner, monkeypatch):
    import pkgutil

    monkeypatch.setattr(
        pkgutil,
        "get_data",
        lambda pkg, resource: b"# Mock Packaged Skill\nDetails here",
    )

    res = runner.invoke(app, ["agent-skill"])
    assert res.exit_code == 0
    assert "Mock Packaged Skill" in res.output


def test_agent_skill_local_file_fallback(runner, monkeypatch, tmp_path):
    import pkgutil

    monkeypatch.setattr(pkgutil, "get_data", MagicMock(side_effect=FileNotFoundError))

    # Real local file exists in src/recon/SKILL.md
    res = runner.invoke(app, ["agent-skill"])
    assert res.exit_code == 0
    assert "Recon" in res.output


def test_agent_skill_file_missing_fallback(runner, monkeypatch):
    import pkgutil

    monkeypatch.setattr(pkgutil, "get_data", MagicMock(side_effect=FileNotFoundError))
    # Mock Path.exists to return False for SKILL.md
    orig_exists = Path.exists
    monkeypatch.setattr(
        Path, "exists", lambda p: False if "SKILL.md" in str(p) else orig_exists(p)
    )

    res = runner.invoke(app, ["agent-skill"])
    assert res.exit_code == 0
    assert "Skill file not found" in res.output


def test_config_command_show(runner, isolated_env):
    res = runner.invoke(app, ["config", "--show"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert "project" in data
    assert "daemon" in data


def test_config_command_no_flags(runner, isolated_env):
    res = runner.invoke(app, ["config"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert "output" in data


def test_config_command_set_project(runner, temp_repo, isolated_env):
    res = runner.invoke(
        app,
        [
            "config",
            "--lang",
            "rust",
            "--repo-path",
            str(temp_repo),
        ],
    )
    assert res.exit_code == 0
    assert "Config saved" in res.output
    data = json.loads(res.output[res.output.find("{") :])
    assert data["project"]["language"] == "rust"
    assert (temp_repo / ".recon.toml").exists()


def test_config_command_set_global(runner, isolated_env):
    res = runner.invoke(
        app,
        [
            "config",
            "--lang",
            "go",
            "--global",
        ],
    )
    assert res.exit_code == 0
    assert "Config saved" in res.output
    data = json.loads(res.output[res.output.find("{") :])
    assert data["project"]["language"] == "go"
    global_file = isolated_env["config"] / "recon" / "config.toml"
    assert global_file.exists()
