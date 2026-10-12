from unittest.mock import MagicMock
import pytest
from typer.testing import CliRunner

from recon.commands.daemon_cmd import app

def test_daemon_start_already_running(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: True)
    res = runner.invoke(app, ["start"])
    assert res.exit_code == 0
    assert "Daemon is already running" in res.output

def test_daemon_start_success(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: False)
    mock_spawn = MagicMock()
    monkeypatch.setattr("recon.commands.daemon_cmd.spawn_daemon", mock_spawn)
    monkeypatch.setattr("recon.commands.daemon_cmd.wait_for_daemon_socket", lambda: True)

    res = runner.invoke(app, ["start"])
    assert res.exit_code == 0
    assert "Daemon started successfully" in res.output
    assert mock_spawn.called

def test_daemon_start_timeout(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: False)
    monkeypatch.setattr("recon.commands.daemon_cmd.spawn_daemon", MagicMock())
    monkeypatch.setattr("recon.commands.daemon_cmd.wait_for_daemon_socket", lambda: False)

    res = runner.invoke(app, ["start"])
    assert res.exit_code == 1
    assert "Daemon did not become ready in time" in res.output

def test_daemon_stop_not_running(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: False)
    res = runner.invoke(app, ["stop"])
    assert res.exit_code == 0
    assert "No daemon is currently running" in res.output

def test_daemon_stop_success(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: True)
    mock_dispatch = MagicMock(return_value="daemon shutting down")
    monkeypatch.setattr("recon.commands.daemon_cmd.dispatch_request", mock_dispatch)

    res = runner.invoke(app, ["stop"])
    assert res.exit_code == 0
    assert "Daemon stopped: daemon shutting down" in res.output

def test_daemon_stop_failure(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: True)
    monkeypatch.setattr("recon.commands.daemon_cmd.dispatch_request", MagicMock(side_effect=Exception("Socket broke")))

    res = runner.invoke(app, ["stop"])
    assert res.exit_code == 1
    assert "Failed to stop daemon: Socket broke" in res.output

def test_daemon_status_not_running(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: False)
    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0
    assert "Daemon is not running" in res.output

def test_daemon_status_running_with_cached_lsps(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: True)
    mock_dispatch = MagicMock(return_value={
        "cached_lsps": [
            {"lang": "python", "repo_path": "/repo/a", "memory_mb": 42.5},
            {"lang": "rust", "repo_path": "/repo/b", "memory_mb": 0.0},
        ],
        "total_memory_mb": 42.5,
    })
    monkeypatch.setattr("recon.commands.daemon_cmd.dispatch_request", mock_dispatch)

    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0
    assert "Daemon is running" in res.output
    assert "42.5 MB total memory" in res.output
    assert "python" in res.output
    assert "rust" in res.output

def test_daemon_status_running_empty_cache(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: True)
    mock_dispatch = MagicMock(return_value={
        "cached_lsps": [],
        "total_memory_mb": 15.0,
    })
    monkeypatch.setattr("recon.commands.daemon_cmd.dispatch_request", mock_dispatch)

    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0
    assert "Daemon is running" in res.output
    assert "No LSP instances cached yet" in res.output

def test_daemon_status_unreachable_exception(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: True)
    monkeypatch.setattr("recon.commands.daemon_cmd.dispatch_request", MagicMock(side_effect=Exception("Timeout")))

    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0
    assert "Daemon is running but unreachable" in res.output

def test_daemon_restart_success(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: True)
    monkeypatch.setattr("recon.commands.daemon_cmd.dispatch_request", MagicMock())
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr("recon.commands.daemon_cmd.spawn_daemon", MagicMock())
    monkeypatch.setattr("recon.commands.daemon_cmd.wait_for_daemon_socket", lambda: True)

    res = runner.invoke(app, ["restart"])
    assert res.exit_code == 0
    assert "Daemon stopped." in res.output
    assert "Daemon restarted successfully." in res.output

def test_daemon_restart_failure(runner, monkeypatch):
    monkeypatch.setattr("recon.commands.daemon_cmd.is_daemon_alive", lambda: False)
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr("recon.commands.daemon_cmd.spawn_daemon", MagicMock())
    monkeypatch.setattr("recon.commands.daemon_cmd.wait_for_daemon_socket", lambda: False)

    res = runner.invoke(app, ["restart"])
    assert res.exit_code == 1
    assert "Daemon did not restart in time." in res.output
