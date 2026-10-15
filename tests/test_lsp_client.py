import dataclasses
import os
import socket
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from recon.lsp.client import (
    _direct_lsp_request,
    _handle_setup_error,
    _json_default,
    _recvall,
    connect_to_daemon,
    dispatch_lsp_request,
    dispatch_request,
    get_daemon_dir,
    get_daemon_python_executable,
    get_log_file,
    get_pid_file,
    get_port_file,
    get_sock_file,
    is_daemon_alive,
    recv_frame,
    release_daemon_pid,
    send_frame,
    spawn_daemon,
    try_claim_daemon_pid,
    wait_for_daemon_socket,
)


@dataclasses.dataclass
class SimpleData:
    foo: str


def test_get_daemon_dir_platforms(monkeypatch, tmp_path):
    # Linux with XDG_RUNTIME_DIR
    monkeypatch.setattr(sys, "platform", "linux")
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
    d = get_daemon_dir()
    assert d == runtime_dir / "recon"

    # Linux without XDG_RUNTIME_DIR
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(Path, "home", lambda: home_dir)
    d = get_daemon_dir()
    assert d == home_dir / ".local" / "share" / "recon"

    # Darwin (macOS)
    monkeypatch.setattr(sys, "platform", "darwin")
    d = get_daemon_dir()
    assert d == home_dir / "Library" / "Application Support" / "recon"

    # Windows
    monkeypatch.setattr(sys, "platform", "win32")
    local_app_data = tmp_path / "appdata"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    d = get_daemon_dir()
    assert d == local_app_data / "recon"


def test_daemon_file_getters(isolated_env):
    pid = get_pid_file()
    port = get_port_file()
    sock = get_sock_file()
    log = get_log_file()
    assert pid.name == "daemon.pid"
    assert port.name == "daemon.port"
    assert sock.name == "daemon.sock"
    assert log.name == "daemon.log"


def test_json_default():
    obj = SimpleData(foo="bar")
    assert _json_default(obj) == {"foo": "bar"}
    with pytest.raises(TypeError, match="is not JSON serializable"):
        _json_default(object())


def test_send_and_recv_frame():
    # Create a connected socket pair
    server_sock, client_sock = socket.socketpair()
    try:
        payload = {
            "cmd": "definition",
            "lang": "python",
            "data": SimpleData(foo="test"),
        }
        send_frame(client_sock, payload)
        received = recv_frame(server_sock)
        assert received == {
            "cmd": "definition",
            "lang": "python",
            "data": {"foo": "test"},
        }
    finally:
        server_sock.close()
        client_sock.close()


def test_recv_frame_connection_reset_header():
    server_sock, client_sock = socket.socketpair()
    try:
        client_sock.close()
        with pytest.raises(ConnectionResetError, match="Daemon closed the connection."):
            recv_frame(server_sock)
    finally:
        server_sock.close()


def test_recv_frame_connection_reset_mid_frame():
    server_sock, client_sock = socket.socketpair()
    try:
        # Send only header indicating 50 bytes, then close immediately
        header = struct.pack(">I", 50)
        client_sock.sendall(header)
        client_sock.close()
        with pytest.raises(
            ConnectionResetError, match="Daemon closed the connection mid-frame."
        ):
            recv_frame(server_sock)
    finally:
        server_sock.close()


def test_recvall_partial():
    server_sock, client_sock = socket.socketpair()
    try:
        client_sock.sendall(b"12345")
        client_sock.close()
        # Requesting 10 bytes when only 5 sent
        res = _recvall(server_sock, 10)
        assert res == b""
    finally:
        server_sock.close()


def test_is_daemon_alive_no_pid(isolated_env):
    pid_file = get_pid_file()
    if pid_file.exists():
        pid_file.unlink()
    assert not is_daemon_alive()


def test_is_daemon_alive_running(isolated_env, monkeypatch):
    pid_file = get_pid_file()
    pid_file.write_text(str(os.getpid()))

    mock_proc = MagicMock()
    mock_proc.is_running.return_value = True
    mock_proc.status.return_value = "running"

    import psutil

    monkeypatch.setattr(psutil, "Process", lambda pid: mock_proc)
    assert is_daemon_alive()


def test_is_daemon_alive_dead_process_cleans_pid(isolated_env, monkeypatch):
    pid_file = get_pid_file()
    pid_file.write_text("999999")

    import psutil

    def fake_process(pid):
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", fake_process)
    assert not is_daemon_alive()
    assert not pid_file.exists()


def test_try_claim_daemon_pid_and_release(isolated_env):
    assert try_claim_daemon_pid() is True
    # Second claim should fail
    assert try_claim_daemon_pid() is False
    release_daemon_pid()
    assert not get_pid_file().exists()
    # Can claim again after release
    assert try_claim_daemon_pid() is True
    release_daemon_pid()


def test_connect_to_daemon_unix(isolated_env, monkeypatch):
    monkeypatch.setattr("recon.lsp.client._USE_UNIX_SOCKET", True)
    sock_path = get_sock_file()
    # Bind a temporary unix socket
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        srv.bind(str(sock_path))
        srv.listen(1)
        client = connect_to_daemon()
        assert client is not None
        client.close()
    finally:
        srv.close()
        if sock_path.exists():
            sock_path.unlink()


def test_connect_to_daemon_tcp(isolated_env, monkeypatch):
    monkeypatch.setattr("recon.lsp.client._USE_UNIX_SOCKET", False)
    port_file = get_port_file()

    # Missing port file
    if port_file.exists():
        port_file.unlink()
    with pytest.raises(ConnectionRefusedError, match="Daemon port file not found"):
        connect_to_daemon()

    # Port == 0
    port_file.write_text("0")
    with pytest.raises(ConnectionRefusedError, match="Daemon port not yet assigned"):
        connect_to_daemon()

    # Valid port
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("localhost", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        port_file.write_text(str(port))

        client = connect_to_daemon()
        assert client is not None
        client.close()
    finally:
        srv.close()


def test_wait_for_daemon_socket(isolated_env, monkeypatch):
    # Simulate successful ping-pong
    server_sock, client_sock = socket.socketpair()

    def fake_connect():
        return client_sock

    monkeypatch.setattr("recon.lsp.client.connect_to_daemon", fake_connect)
    monkeypatch.setattr("recon.lsp.client.SPAWN_TIMEOUT", 1.0)
    monkeypatch.setattr("recon.lsp.client.SOCKET_POLL_INTERVAL", 0.01)

    # In a background thread, handle the ping request
    import threading

    def respond():
        req = recv_frame(server_sock)
        if req.get("cmd") == "ping":
            send_frame(server_sock, {"status": "ok", "result": "pong"})

    t = threading.Thread(target=respond)
    t.start()

    ready = wait_for_daemon_socket()
    t.join()
    server_sock.close()
    assert ready is True


def test_wait_for_daemon_socket_timeout(monkeypatch):
    def fake_connect():
        raise ConnectionRefusedError()

    monkeypatch.setattr("recon.lsp.client.connect_to_daemon", fake_connect)
    monkeypatch.setattr("recon.lsp.client.SPAWN_TIMEOUT", 0.05)
    monkeypatch.setattr("recon.lsp.client.SOCKET_POLL_INTERVAL", 0.01)

    assert wait_for_daemon_socket() is False


def test_get_daemon_python_executable(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    venv_bin = tmp_path / "bin"
    venv_bin.mkdir(parents=True)
    fake_python = venv_bin / "python"
    fake_python.touch()
    monkeypatch.setattr(sys, "prefix", str(tmp_path))

    exe = get_daemon_python_executable()
    assert exe == str(fake_python)

    # Windows venv
    monkeypatch.setattr(sys, "platform", "win32")
    venv_scripts = tmp_path / "Scripts"
    venv_scripts.mkdir(parents=True)
    fake_win_python = venv_scripts / "python.exe"
    fake_win_python.touch()

    exe_win = get_daemon_python_executable()
    assert exe_win == str(fake_win_python)


def test_spawn_daemon(monkeypatch):
    mock_popen = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)
    spawn_daemon()
    assert mock_popen.called


def test_handle_setup_error():
    with pytest.raises(RuntimeError) as exc_info:
        _handle_setup_error("python", "Command not found")
    assert "Command not found" in str(exc_info.value)
    assert "pip install jedi-language-server" in str(exc_info.value)


def test_dispatch_request_success(monkeypatch):
    server_sock, client_sock = socket.socketpair()
    monkeypatch.setattr("recon.lsp.client.connect_to_daemon", lambda: client_sock)

    import threading

    def handle():
        req = recv_frame(server_sock)
        assert req["cmd"] == "definition"
        send_frame(server_sock, {"status": "ok", "result": [{"line": 10}]})

    t = threading.Thread(target=handle)
    t.start()

    res = dispatch_request({"cmd": "definition"})
    t.join()
    server_sock.close()
    assert res == [{"line": 10}]


def test_dispatch_request_error_response(monkeypatch):
    server_sock, client_sock = socket.socketpair()
    monkeypatch.setattr("recon.lsp.client.connect_to_daemon", lambda: client_sock)

    import threading

    def handle():
        recv_frame(server_sock)
        send_frame(server_sock, {"status": "error", "error": "Internal error"})

    t = threading.Thread(target=handle)
    t.start()

    with pytest.raises(RuntimeError, match="Internal error"):
        dispatch_request({"cmd": "bad"})
    t.join()
    server_sock.close()


def test_dispatch_request_setup_error_response(monkeypatch):
    server_sock, client_sock = socket.socketpair()
    monkeypatch.setattr("recon.lsp.client.connect_to_daemon", lambda: client_sock)

    import threading

    def handle():
        recv_frame(server_sock)
        send_frame(
            server_sock,
            {"status": "setup_error", "lang": "python", "error": "Binary missing"},
        )

    t = threading.Thread(target=handle)
    t.start()

    with pytest.raises(RuntimeError, match="Binary missing"):
        dispatch_request({"cmd": "definition"})
    t.join()
    server_sock.close()


def test_dispatch_request_auto_spawns_daemon(monkeypatch):
    attempt = 0
    server_sock, client_sock = socket.socketpair()

    def fake_connect():
        nonlocal attempt
        if attempt == 0:
            attempt += 1
            raise ConnectionRefusedError()
        return client_sock

    monkeypatch.setattr("recon.lsp.client.connect_to_daemon", fake_connect)
    monkeypatch.setattr("recon.lsp.client.is_daemon_alive", lambda: False)
    mock_spawn = MagicMock()
    monkeypatch.setattr("recon.lsp.client.spawn_daemon", mock_spawn)
    monkeypatch.setattr("recon.lsp.client.wait_for_daemon_socket", lambda: True)

    import threading

    def handle():
        recv_frame(server_sock)
        send_frame(server_sock, {"status": "ok", "result": "success"})

    t = threading.Thread(target=handle)
    t.start()

    res = dispatch_request({"cmd": "test"})
    t.join()
    server_sock.close()
    assert res == "success"
    assert mock_spawn.called


def test_dispatch_request_spawn_timeout(monkeypatch):
    monkeypatch.setattr(
        "recon.lsp.client.connect_to_daemon",
        MagicMock(side_effect=ConnectionRefusedError),
    )
    monkeypatch.setattr("recon.lsp.client.is_daemon_alive", lambda: False)
    monkeypatch.setattr("recon.lsp.client.spawn_daemon", MagicMock())
    monkeypatch.setattr("recon.lsp.client.wait_for_daemon_socket", lambda: False)

    with pytest.raises(
        RuntimeError, match="Daemon failed to start within the timeout period"
    ):
        dispatch_request({"cmd": "test"})


def test_dispatch_request_second_connect_failure(monkeypatch):
    monkeypatch.setattr(
        "recon.lsp.client.connect_to_daemon",
        MagicMock(side_effect=ConnectionRefusedError),
    )
    monkeypatch.setattr("recon.lsp.client.is_daemon_alive", lambda: True)
    monkeypatch.setattr("recon.lsp.client.wait_for_daemon_socket", lambda: True)

    with pytest.raises(
        RuntimeError, match="Could not connect to daemon after spawning"
    ):
        dispatch_request({"cmd": "test"})


def test_dispatch_lsp_request_routes(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "recon.lsp.client.dispatch_request", lambda p: calls.append(("daemon", p))
    )
    monkeypatch.setattr(
        "recon.lsp.client._direct_lsp_request",
        lambda *a, **k: calls.append(("direct", a, k)),
    )

    dispatch_lsp_request(
        "definition", "python", "/repo", no_daemon=False, file_path="a.py"
    )
    assert calls[0][0] == "daemon"

    dispatch_lsp_request(
        "definition", "python", "/repo", no_daemon=True, file_path="a.py"
    )
    assert calls[1][0] == "direct"


def test_direct_lsp_request_commands(monkeypatch):
    mock_lsp = MagicMock()
    mock_ctx = MagicMock()
    mock_lsp.start_server.return_value = mock_ctx

    mock_sync_cls = MagicMock()
    mock_sync_cls.create.return_value = mock_lsp

    monkeypatch.setattr("multilspy.SyncLanguageServer", mock_sync_cls)

    # Definition
    mock_lsp.request_definition.return_value = [{"def": 1}]
    res = _direct_lsp_request(
        "definition", "python", "/repo", file_path="main.py", line=1, col=2
    )
    assert res == [{"def": 1}]
    mock_lsp.request_definition.assert_called_with("main.py", 1, 2)

    # References
    mock_lsp.request_references.return_value = [{"ref": 1}]
    res = _direct_lsp_request(
        "references", "python", "/repo", file_path="main.py", line=1, col=2
    )
    assert res == [{"ref": 1}]

    # Hover
    mock_lsp.request_hover.return_value = {"contents": "docs"}
    res = _direct_lsp_request(
        "hover", "python", "/repo", file_path="main.py", line=1, col=2
    )
    assert res == {"contents": "docs"}

    # Document symbols
    mock_lsp.request_document_symbols.return_value = ([{"name": "foo"}], None)
    res = _direct_lsp_request(
        "document_symbols", "python", "/repo", file_path="main.py"
    )
    assert res == [{"name": "foo"}]

    # Workspace symbol
    mock_lsp.request_workspace_symbol.return_value = [{"name": "Bar"}]
    res = _direct_lsp_request("workspace_symbol", "python", "/repo", query="Bar")
    assert res == [{"name": "Bar"}]

    # Completions
    mock_lsp.request_completions.return_value = [{"label": "baz"}]
    res = _direct_lsp_request(
        "completions", "python", "/repo", file_path="main.py", line=1, col=2
    )
    assert res == [{"label": "baz"}]

    # Unknown command
    with pytest.raises(ValueError, match="Unknown command: unknown_cmd"):
        _direct_lsp_request("unknown_cmd", "python", "/repo")


def test_direct_lsp_request_startup_failure(monkeypatch):
    mock_sync_cls = MagicMock()
    mock_sync_cls.create.side_effect = Exception("Multilspy setup error")
    monkeypatch.setattr("multilspy.SyncLanguageServer", mock_sync_cls)

    with pytest.raises(RuntimeError, match="Multilspy setup error"):
        _direct_lsp_request(
            "definition", "python", "/repo", file_path="main.py", line=1, col=2
        )
