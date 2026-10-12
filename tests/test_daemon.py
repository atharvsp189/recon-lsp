import json
import socket
import sys
import threading
import time
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

import recon.daemon as daemon_mod
from recon.daemon import (
    LspEntry,
    _dispatch_lsp_cmd,
    get_or_create_lsp,
    get_memory_mb,
    get_lsp_pid,
    handle_connection,
    _idle_watchdog,
    _cleanup,
    _handle_sigterm,
    run_daemon,
)
from recon.lsp.client import send_frame, recv_frame

def test_lsp_entry_execute_and_stop():
    mock_lsp = MagicMock()
    mock_lsp.request_definition.return_value = [{"def": "test"}]
    mock_stack = MagicMock()

    entry = LspEntry(mock_lsp, mock_stack)
    res = entry.execute("definition", file_path="a.py", line=1, col=2)
    assert res == [{"def": "test"}]

    entry.stop()
    assert mock_stack.close.called

def test_lsp_entry_stop_exception():
    mock_lsp = MagicMock()
    mock_stack = MagicMock()
    mock_stack.close.side_effect = Exception("Stack error")

    entry = LspEntry(mock_lsp, mock_stack)
    # Stop should not raise exception
    entry.stop()

def test_dispatch_lsp_cmd_all_routes():
    mock_lsp = MagicMock()
    mock_lsp.request_definition.return_value = "def"
    mock_lsp.request_references.return_value = "ref"
    mock_lsp.request_hover.return_value = "hov"
    mock_lsp.request_document_symbols.return_value = ("sym", None)
    mock_lsp.request_workspace_symbol.return_value = "ws_sym"
    mock_lsp.request_completions.return_value = "comp"

    assert _dispatch_lsp_cmd(mock_lsp, "definition", file_path="f", line=1, col=2) == "def"
    assert _dispatch_lsp_cmd(mock_lsp, "references", file_path="f", line=1, col=2) == "ref"
    assert _dispatch_lsp_cmd(mock_lsp, "hover", file_path="f", line=1, col=2) == "hov"
    assert _dispatch_lsp_cmd(mock_lsp, "document_symbols", file_path="f") == "sym"
    assert _dispatch_lsp_cmd(mock_lsp, "workspace_symbol", query="q") == "ws_sym"
    assert _dispatch_lsp_cmd(mock_lsp, "completions", file_path="f", line=1, col=2) == "comp"

    with pytest.raises(ValueError, match="Unknown LSP command"):
        _dispatch_lsp_cmd(mock_lsp, "invalid_cmd")

def test_get_or_create_lsp_cached():
    entry_mock = MagicMock()
    key = ("python", "/test/repo")
    with daemon_mod._cache_lock:
        daemon_mod._lsp_cache[key] = entry_mock

    try:
        assert get_or_create_lsp("python", "/test/repo") is entry_mock
    finally:
        with daemon_mod._cache_lock:
            daemon_mod._lsp_cache.clear()

def test_get_or_create_lsp_boots_new(monkeypatch, tmp_path):
    mock_sync_cls = MagicMock()
    mock_lsp = MagicMock()
    mock_ctx = MagicMock()
    mock_lsp.start_server.return_value = mock_ctx
    mock_sync_cls.create.return_value = mock_lsp
    monkeypatch.setattr(daemon_mod, "SyncLanguageServer", mock_sync_cls)

    with daemon_mod._cache_lock:
        daemon_mod._lsp_cache.clear()

    entry = get_or_create_lsp("rust", str(tmp_path))
    try:
        assert entry.lsp is mock_lsp
        assert ("rust", str(tmp_path)) in daemon_mod._lsp_cache
    finally:
        with daemon_mod._cache_lock:
            daemon_mod._lsp_cache.clear()


def test_get_memory_mb(monkeypatch):
    mock_proc = MagicMock()
    mock_proc.memory_info.return_value.rss = 10485760  # 10 MB
    import psutil
    monkeypatch.setattr(psutil, "Process", lambda pid: mock_proc)
    assert get_memory_mb(1234) == 10.0

def test_get_memory_mb_exception(monkeypatch):
    import psutil
    def fake_proc(pid):
        raise psutil.NoSuchProcess(pid)
    monkeypatch.setattr(psutil, "Process", fake_proc)
    assert get_memory_mb(1234) == 0.0

def test_get_lsp_pid():
    entry = MagicMock()
    entry.lsp.language_server.server.process.pid = 4321
    assert get_lsp_pid(entry) == 4321

    bad_entry = MagicMock()
    del bad_entry.lsp
    assert get_lsp_pid(bad_entry) == 0

def test_handle_connection_ping():
    server_sock, client_sock = socket.socketpair()
    send_frame(client_sock, {"cmd": "ping"})
    handle_connection(server_sock)
    resp = recv_frame(client_sock)
    assert resp == {"status": "ok", "result": "pong"}
    client_sock.close()

def test_handle_connection_stop():
    daemon_mod._shutdown_event.clear()
    server_sock, client_sock = socket.socketpair()
    send_frame(client_sock, {"cmd": "stop"})
    handle_connection(server_sock)
    resp = recv_frame(client_sock)
    assert resp == {"status": "ok", "result": "daemon shutting down"}
    assert daemon_mod._shutdown_event.is_set()
    client_sock.close()

def test_handle_connection_status(monkeypatch):
    server_sock, client_sock = socket.socketpair()
    send_frame(client_sock, {"cmd": "status"})

    entry = MagicMock()
    entry.lsp.language_server.server.process.pid = 999
    with daemon_mod._cache_lock:
        daemon_mod._lsp_cache.clear()
        daemon_mod._lsp_cache[("python", "/my/repo")] = entry

    monkeypatch.setattr(daemon_mod, "get_memory_mb", lambda pid: 25.0)

    try:
        handle_connection(server_sock)
        resp = recv_frame(client_sock)
        assert resp["status"] == "ok"
        result = resp["result"]
        assert result["total_memory_mb"] > 0
        assert len(result["cached_lsps"]) == 1
        assert result["cached_lsps"][0]["lang"] == "python"
    finally:
        client_sock.close()
        with daemon_mod._cache_lock:
            daemon_mod._lsp_cache.clear()

def test_handle_connection_missing_lang_or_repo():
    server_sock, client_sock = socket.socketpair()
    send_frame(client_sock, {"cmd": "definition", "lang": "python"})  # missing repo_path
    handle_connection(server_sock)
    resp = recv_frame(client_sock)
    assert resp["status"] == "error"
    assert "Missing 'lang' or 'repo_path'" in resp["error"]
    client_sock.close()

def test_handle_connection_lsp_boot_failure(monkeypatch):
    server_sock, client_sock = socket.socketpair()
    send_frame(client_sock, {"cmd": "definition", "lang": "bad_lang", "repo_path": "/repo"})

    def fake_boot(lang, repo):
        raise RuntimeError("Failed to boot language server")

    monkeypatch.setattr(daemon_mod, "get_or_create_lsp", fake_boot)

    handle_connection(server_sock)
    resp = recv_frame(client_sock)
    assert resp["status"] == "setup_error"
    assert resp["lang"] == "bad_lang"
    assert "Failed to boot language server" in resp["error"]
    client_sock.close()

def test_handle_connection_command_execution(monkeypatch):
    server_sock, client_sock = socket.socketpair()
    send_frame(client_sock, {
        "cmd": "definition",
        "lang": "python",
        "repo_path": "/repo",
        "file_path": "main.py",
        "line": 1,
        "col": 2,
    })

    mock_entry = MagicMock()
    mock_entry.execute.return_value = [{"location": "found"}]
    monkeypatch.setattr(daemon_mod, "get_or_create_lsp", lambda lang, repo: mock_entry)

    handle_connection(server_sock)
    resp = recv_frame(client_sock)
    assert resp["status"] == "ok"
    assert resp["result"] == [{"location": "found"}]
    client_sock.close()

def test_handle_connection_exception_during_execution(monkeypatch):
    server_sock, client_sock = socket.socketpair()
    send_frame(client_sock, {
        "cmd": "definition",
        "lang": "python",
        "repo_path": "/repo",
        "file_path": "main.py",
        "line": 1,
        "col": 2,
    })

    mock_entry = MagicMock()
    mock_entry.execute.side_effect = Exception("LSP internal crash")
    monkeypatch.setattr(daemon_mod, "get_or_create_lsp", lambda lang, repo: mock_entry)

    handle_connection(server_sock)
    resp = recv_frame(client_sock)
    assert resp["status"] == "error"
    assert "LSP internal crash" in resp["error"]
    client_sock.close()

def test_idle_watchdog_timeout(monkeypatch):
    daemon_mod._shutdown_event.clear()
    monkeypatch.setattr(daemon_mod, "IDLE_TIMEOUT_SECONDS", 0.05)
    daemon_mod._last_request_time = time.monotonic() - 10.0  # past timeout

    _idle_watchdog()
    assert daemon_mod._shutdown_event.is_set()

def test_cleanup(isolated_env):
    mock_entry = MagicMock()
    with daemon_mod._cache_lock:
        daemon_mod._lsp_cache[("python", "/repo")] = mock_entry

    _cleanup()
    assert mock_entry.stop.called
    assert len(daemon_mod._lsp_cache) == 0

def test_handle_sigterm():
    daemon_mod._shutdown_event.clear()
    _handle_sigterm(15, None)
    assert daemon_mod._shutdown_event.is_set()

def test_run_daemon_already_running(monkeypatch):
    monkeypatch.setattr(daemon_mod, "try_claim_daemon_pid", lambda: False)
    with pytest.raises(SystemExit) as exc_info:
        run_daemon()
    assert exc_info.value.code == 0

def test_run_daemon_unix_socket_lifecycle(isolated_env, monkeypatch):
    monkeypatch.setattr(daemon_mod, "try_claim_daemon_pid", lambda: True)
    monkeypatch.setattr(daemon_mod, "_USE_UNIX_SOCKET", True)
    
    daemon_mod._shutdown_event.clear()

    # Trigger shutdown after short delay
    def trigger_shutdown():
        time.sleep(0.1)
        daemon_mod._shutdown_event.set()

    orig_settimeout = socket.socket.settimeout
    monkeypatch.setattr(socket.socket, "settimeout", lambda self, val: orig_settimeout(self, 0.05))

    t = threading.Thread(target=trigger_shutdown)
    t.start()

    run_daemon()
    t.join()

def test_run_daemon_tcp_socket_lifecycle(isolated_env, monkeypatch):
    monkeypatch.setattr(daemon_mod, "try_claim_daemon_pid", lambda: True)
    monkeypatch.setattr(daemon_mod, "_USE_UNIX_SOCKET", False)
    
    daemon_mod._shutdown_event.clear()

    orig_settimeout = socket.socket.settimeout
    monkeypatch.setattr(socket.socket, "settimeout", lambda self, val: orig_settimeout(self, 0.05))

    def trigger_shutdown():
        time.sleep(0.05)
        daemon_mod._shutdown_event.set()

    t = threading.Thread(target=trigger_shutdown)
    t.start()

    run_daemon()
    t.join()

