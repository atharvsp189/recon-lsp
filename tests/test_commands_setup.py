import json
import shutil
import sys
from unittest.mock import MagicMock
from pathlib import Path
import pytest
from typer.testing import CliRunner

from recon.commands.setup_cmd import (
    app,
    setup,
    check_prerequisites,
    check_server_binary,
    verify_server_probe,
    install_server,
    _show_all_languages_diagnostics,
    LANGUAGE_METADATA,
)


def test_check_prerequisites_all_found(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    ok, found, missing = check_prerequisites("python")
    assert ok is True
    assert "python3" in found
    assert "pip" in found
    assert len(missing) == 0

def test_check_prerequisites_with_pip3_and_python_fallbacks(monkeypatch):
    def fake_which(cmd):
        if cmd in ("python", "pip3"):
            return f"/usr/bin/{cmd}"
        return None

    monkeypatch.setattr(shutil, "which", fake_which)
    ok, found, missing = check_prerequisites("python")
    assert ok is True
    assert "python" in found
    assert "pip3" in found

def test_check_prerequisites_missing(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    ok, found, missing = check_prerequisites("rust")
    assert ok is False
    assert "rustc" in missing
    assert "cargo" in missing

def test_check_server_binary_found_in_path(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda b: f"/usr/bin/{b}")
    has_bin, bin_path = check_server_binary("rust")
    assert has_bin is True
    assert bin_path == "/usr/bin/rust-analyzer"

def test_check_server_binary_in_multilspy_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda b: None)
    cache_dir = tmp_path / ".multilspy" / "lsp" / "servers" / "go"
    cache_dir.mkdir(parents=True)
    fake_bin = cache_dir / "gopls_server"
    fake_bin.touch()

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("os.access", lambda path, mode: True)

    has_bin, bin_path = check_server_binary("go")
    assert has_bin is True
    assert "gopls_server" in bin_path

def test_check_server_binary_python_module(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda b: None)
    monkeypatch.setattr(Path, "home", lambda: Path("/nonexistent"))

    # When jedi_language_server is importable
    has_bin, bin_path = check_server_binary("python")
    assert has_bin is True
    assert "jedi_language_server" in bin_path

def test_check_server_binary_not_found(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda b: None)
    monkeypatch.setattr(Path, "home", lambda: Path("/nonexistent"))

    # For language like ruby with solargraph not installed
    has_bin, bin_path = check_server_binary("ruby")
    assert has_bin is False
    assert bin_path is None

def test_verify_server_probe_success(monkeypatch):
    mock_sync_cls = MagicMock()
    mock_lsp = MagicMock()
    mock_ctx = MagicMock()
    mock_lsp.start_server.return_value = mock_ctx
    mock_sync_cls.create.return_value = mock_lsp
    monkeypatch.setattr("multilspy.SyncLanguageServer", mock_sync_cls)

    ok, msg = verify_server_probe("python")
    assert ok is True
    assert "handshake successfully" in msg

def test_verify_server_probe_failure(monkeypatch):
    mock_sync_cls = MagicMock()
    mock_sync_cls.create.side_effect = Exception("Probe crashed")
    monkeypatch.setattr("multilspy.SyncLanguageServer", mock_sync_cls)

    ok, msg = verify_server_probe("python")
    assert ok is False
    assert "Probe crashed" in msg

def test_install_server_prereqs_missing(monkeypatch):
    monkeypatch.setattr("recon.commands.setup_cmd.check_prerequisites", lambda lang: (False, [], ["cargo"]))
    ok, msg = install_server("rust")
    assert ok is False
    assert "Missing system prerequisite tools: cargo" in msg

def test_install_server_mvp_disabled(monkeypatch):
    monkeypatch.setattr("recon.commands.setup_cmd.check_prerequisites", lambda lang: (True, ["python3", "pip"], []))
    ok, msg = install_server("python")
    assert ok is False
    assert "Automated installation is currently disabled" in msg

def test_setup_no_arg_shows_all_table(runner):
    res = runner.invoke(app, [])
    assert res.exit_code == 0
    assert "Recon Language Server Diagnostics" in res.output
    assert "python" in res.output
    assert "rust" in res.output

def test_setup_no_arg_as_json(runner):
    res = runner.invoke(app, ["--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert isinstance(data, list)
    assert len(data) == 12
    assert any(item["language"] == "python" for item in data)

@pytest.fixture
def cli_app():
    import typer
    c = typer.Typer()
    c.command()(setup)
    return c

def test_setup_unknown_language(runner, cli_app):
    res = runner.invoke(cli_app, ["unknown_lang"])
    assert res.exit_code == 1
    assert "Unknown language 'unknown_lang'" in res.output

def test_setup_single_lang_json_mode(runner, cli_app, monkeypatch):
    monkeypatch.setattr("recon.commands.setup_cmd.check_prerequisites", lambda l: (True, ["python3"], []))
    monkeypatch.setattr("recon.commands.setup_cmd.check_server_binary", lambda l: (True, "/bin/jedi"))
    monkeypatch.setattr("recon.commands.setup_cmd.verify_server_probe", lambda l, r: (True, "OK"))

    res = runner.invoke(cli_app, ["python", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["language"] == "python"
    assert data["binary_detected"] is True
    assert data["probe_verified"] is True

def test_setup_single_lang_verify_only_success(runner, cli_app, monkeypatch):
    monkeypatch.setattr("recon.commands.setup_cmd.verify_server_probe", lambda l, r: (True, "OK"))
    res = runner.invoke(cli_app, ["python", "--verify"])
    assert res.exit_code == 0
    assert "is installed and working!" in res.output

def test_setup_single_lang_verify_only_failure(runner, cli_app, monkeypatch):
    monkeypatch.setattr("recon.commands.setup_cmd.verify_server_probe", lambda l, r: (False, "LSP timeout"))
    res = runner.invoke(cli_app, ["python", "--verify"])
    assert res.exit_code == 1
    assert "Verification failed: LSP timeout" in res.output

def test_setup_single_lang_verify_only_json_failure(runner, cli_app, monkeypatch):
    monkeypatch.setattr("recon.commands.setup_cmd.check_prerequisites", lambda l: (False, [], ["java"]))
    monkeypatch.setattr("recon.commands.setup_cmd.check_server_binary", lambda l: (False, None))
    monkeypatch.setattr("recon.commands.setup_cmd.verify_server_probe", lambda l, r: (False, "Fail"))

    res = runner.invoke(cli_app, ["java", "--verify", "--json"])
    assert res.exit_code == 1
    data = json.loads(res.output)
    assert data["probe_verified"] is False

def test_setup_single_lang_interactive_probe_success(runner, cli_app, monkeypatch):
    monkeypatch.setattr("recon.commands.setup_cmd.check_prerequisites", lambda l: (True, ["cargo"], []))
    monkeypatch.setattr("recon.commands.setup_cmd.check_server_binary", lambda l: (True, "/bin/rust-analyzer"))
    monkeypatch.setattr("recon.commands.setup_cmd.verify_server_probe", lambda l, r: (True, "OK"))

    res = runner.invoke(cli_app, ["rust"])
    assert res.exit_code == 0
    assert "Language Server Diagnostics: RUST" in res.output
    assert "is fully operational!" in res.output

def test_setup_single_lang_interactive_probe_failure(runner, cli_app, monkeypatch):
    monkeypatch.setattr("recon.commands.setup_cmd.check_prerequisites", lambda l: (False, [], ["solargraph"]))
    monkeypatch.setattr("recon.commands.setup_cmd.check_server_binary", lambda l: (False, None))
    monkeypatch.setattr("recon.commands.setup_cmd.verify_server_probe", lambda l, r: (False, "Solargraph missing"))

    res = runner.invoke(cli_app, ["ruby"])
    assert res.exit_code == 0
    assert "Server probe failed: Solargraph missing" in res.output
    assert "Manual installation instructions:" in res.output

def test_setup_with_install_flag_failure(runner, cli_app, monkeypatch):
    monkeypatch.setattr("recon.commands.setup_cmd.check_prerequisites", lambda l: (True, ["go"], []))
    monkeypatch.setattr("recon.commands.setup_cmd.check_server_binary", lambda l: (False, None))
    monkeypatch.setattr("recon.commands.setup_cmd.install_server", lambda l, r: (False, "Disabled"))

    res = runner.invoke(cli_app, ["go", "--install"])
    assert res.exit_code == 1
    assert "Installation failed: Disabled" in res.output

