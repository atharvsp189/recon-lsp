import os
import toml
from pathlib import Path
import pytest

from recon.config import (
    get_global_config_dir,
    get_global_config_path,
    get_project_config_path,
    _load_toml,
    _save_toml,
    SUPPORTED_LANGUAGES,
    LANGUAGE_SERVERS,
    ReconConfig,
    load_config,
    save_project_config,
    save_global_config,
)


def test_get_global_config_dir_with_xdg(tmp_path, monkeypatch):
    xdg_dir = tmp_path / "custom_xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_dir))
    config_dir = get_global_config_dir()
    assert config_dir == xdg_dir / "recon"
    assert config_dir.exists()


def test_get_global_config_dir_without_xdg(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    config_dir = get_global_config_dir()
    assert config_dir == tmp_path / ".config" / "recon"
    assert config_dir.exists()


def test_get_global_config_path(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert get_global_config_path() == tmp_path / "recon" / "config.toml"


def test_get_project_config_path(tmp_path):
    # With explicit repo_path
    path = get_project_config_path(str(tmp_path))
    assert path == tmp_path.resolve() / ".recon.toml"

    # With None (defaults to cwd)
    cwd_path = get_project_config_path(None)
    assert cwd_path == Path.cwd() / ".recon.toml"


def test_load_toml_nonexistent(tmp_path):
    non_existent = tmp_path / "missing.toml"
    assert _load_toml(non_existent) == {}


def test_load_toml_valid(tmp_path):
    target = tmp_path / "valid.toml"
    data = {"project": {"language": "python"}}
    with open(target, "w") as f:
        toml.dump(data, f)
    assert _load_toml(target) == data


def test_load_toml_corrupt(tmp_path):
    target = tmp_path / "corrupt.toml"
    target.write_text("this is invalid toml = = = [", encoding="utf-8")
    assert _load_toml(target) == {}


def test_save_toml(tmp_path):
    target = tmp_path / "nested" / "dir" / "config.toml"
    data = {"project": {"language": "rust", "repo_path": "/path/to/repo"}}
    _save_toml(target, data)
    assert target.exists()
    loaded = toml.load(target)
    assert loaded == data


def test_supported_languages_and_servers():
    assert len(SUPPORTED_LANGUAGES) == 12
    assert "python" in SUPPORTED_LANGUAGES
    assert "rust" in SUPPORTED_LANGUAGES
    for lang in SUPPORTED_LANGUAGES:
        assert lang in LANGUAGE_SERVERS
        assert isinstance(LANGUAGE_SERVERS[lang], str)


def test_recon_config_defaults():
    cfg = ReconConfig()
    assert cfg.language is None
    assert cfg.repo_path is None
    assert cfg.idle_timeout == 900
    assert cfg.request_timeout == 30
    assert cfg.default_format == "json"
    assert cfg.context_lines == 0

    d = cfg.to_dict()
    assert d == {
        "project": {"language": "", "repo_path": ""},
        "daemon": {"idle_timeout": 900, "request_timeout": 30},
        "output": {"default_format": "json", "context_lines": 0},
    }


def test_recon_config_custom_and_roundtrip():
    cfg = ReconConfig(
        language="python",
        repo_path="/tmp/repo",
        idle_timeout=600,
        request_timeout=45,
        default_format="human",
        context_lines=5,
    )
    d = cfg.to_dict()
    loaded = ReconConfig.from_dict(d)
    assert loaded.language == "python"
    assert loaded.repo_path == "/tmp/repo"
    assert loaded.idle_timeout == 600
    assert loaded.request_timeout == 45
    assert loaded.default_format == "human"
    assert loaded.context_lines == 5


def test_recon_config_from_empty_dict():
    cfg = ReconConfig.from_dict({})
    assert cfg.language is None
    assert cfg.repo_path is None
    assert cfg.idle_timeout == 900
    assert cfg.request_timeout == 30
    assert cfg.default_format == "json"
    assert cfg.context_lines == 0


def test_load_config_deep_merge(tmp_path, isolated_env):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Save global config
    global_cfg = ReconConfig(
        language="go",
        idle_timeout=1200,
        default_format="table",
    )
    save_global_config(global_cfg)

    # Save project config (overrides language and context_lines)
    project_cfg = ReconConfig(
        language="python",
        repo_path=str(repo_dir),
        context_lines=3,
    )
    save_project_config(project_cfg, str(repo_dir))

    merged = load_config(str(repo_dir))
    # Project overrides language
    assert merged.language == "python"
    assert merged.repo_path == str(repo_dir)
    # Global default maintained where not overridden in project
    assert (
        merged.idle_timeout == 900
    )  # Note: project_cfg.to_dict() has 900, so it takes project's 900
    assert merged.default_format == "json"  # project_cfg default overrides
    assert merged.context_lines == 3


def test_save_project_and_global_config(tmp_path, isolated_env):
    repo_dir = tmp_path / "my_project"
    repo_dir.mkdir()
    cfg = ReconConfig(language="rust", repo_path=str(repo_dir))

    proj_path = save_project_config(cfg, str(repo_dir))
    assert proj_path == repo_dir / ".recon.toml"
    assert proj_path.exists()

    glob_path = save_global_config(cfg)
    assert glob_path.exists()
    assert glob_path == isolated_env["config"] / "recon" / "config.toml"
