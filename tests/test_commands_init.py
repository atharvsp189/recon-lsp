from unittest.mock import MagicMock
from pathlib import Path
import pytest
from typer.testing import CliRunner

from recon.commands.init_cmd import app, _display_languages
from recon.config import save_project_config, ReconConfig, load_config

def test_display_languages(capsys):
    _display_languages()
    captured = capsys.readouterr()
    assert "Supported Languages" in captured.out
    assert "python" in captured.out
    assert "rust" in captured.out

def test_init_non_interactive_success(runner, tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    monkeypatch.setattr("recon.commands.init_cmd.verify_server_probe", lambda lang, path: (True, "OK"))

    res = runner.invoke(app, [
        "--repo-path", str(repo_dir),
        "--lang", "python",
    ])
    assert res.exit_code == 0
    assert "Configuration saved" in res.output
    assert "Setup complete!" in res.output
    assert (repo_dir / ".recon.toml").exists()
    cfg = load_config(str(repo_dir))
    assert cfg.language == "python"

def test_init_existing_config_cancel(runner, tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    cfg = ReconConfig(language="rust", repo_path=str(repo_dir))
    save_project_config(cfg, str(repo_dir))

    # User inputs "n" to not overwrite
    res = runner.invoke(app, ["--repo-path", str(repo_dir)], input="n\n")
    assert res.exit_code == 0
    assert "Existing config found" in res.output
    assert "Setup cancelled. Existing config preserved." in res.output

def test_init_existing_config_overwrite(runner, tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    cfg = ReconConfig(language="rust", repo_path=str(repo_dir))
    save_project_config(cfg, str(repo_dir))

    monkeypatch.setattr("recon.commands.init_cmd.verify_server_probe", lambda lang, path: (True, "OK"))

    # Overwrite = "y", then select language = "python"
    res = runner.invoke(app, ["--repo-path", str(repo_dir)], input="y\npython\n")
    assert res.exit_code == 0
    assert "Configuration saved" in res.output
    new_cfg = load_config(str(repo_dir))
    assert new_cfg.language == "python"

def test_init_interactive_lang_selection_by_number(runner, tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    monkeypatch.setattr("recon.commands.init_cmd.verify_server_probe", lambda lang, path: (True, "OK"))

    # Input "2" corresponds to rust
    res = runner.invoke(app, ["--repo-path", str(repo_dir), "--skip-verify"], input="2\n")
    assert res.exit_code == 0
    new_cfg = load_config(str(repo_dir))
    assert new_cfg.language == "rust"

def test_init_interactive_lang_invalid_then_valid(runner, tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Input: invalid number 999, invalid name "fake_lang", then valid "python"
    res = runner.invoke(
        app,
        ["--repo-path", str(repo_dir), "--skip-verify"],
        input="999\nfake_lang\npython\n",
    )
    assert res.exit_code == 0
    assert "Invalid number. Try again." in res.output
    assert "Unknown language 'fake_lang'. Try again." in res.output
    new_cfg = load_config(str(repo_dir))
    assert new_cfg.language == "python"

def test_init_interactive_repo_prompt(runner, tmp_path, monkeypatch):
    repo_dir = tmp_path / "interactive_repo"
    repo_dir.mkdir()

    # First prompt is repo path, then lang
    res = runner.invoke(
        app,
        ["--lang", "python", "--skip-verify"],
        input=f"{repo_dir}\n",
    )
    assert res.exit_code == 0
    assert (repo_dir / ".recon.toml").exists()

def test_init_probe_failure_continue_confirmed(runner, tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    monkeypatch.setattr("recon.commands.init_cmd.verify_server_probe", lambda lang, path: (False, "Probe failed"))

    # When probe fails, Confirm.ask("Continue configuration anyway?", default=True) -> input "y"
    res = runner.invoke(app, ["--repo-path", str(repo_dir), "--lang", "go"], input="y\n")
    assert res.exit_code == 0
    assert "Language server verification probe reported" in res.output
    assert "Configuration saved" in res.output

def test_init_probe_failure_continue_aborted(runner, tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    monkeypatch.setattr("recon.commands.init_cmd.verify_server_probe", lambda lang, path: (False, "Probe failed"))

    # Decline to continue -> input "n"
    res = runner.invoke(app, ["--repo-path", str(repo_dir), "--lang", "go"], input="n\n")
    assert res.exit_code == 1
    assert "Language server verification probe reported" in res.output
