"""
client.py — LSP client layer for recon.

Provides two execution modes:
  1. Daemon mode (default): Routes requests through a persistent background
     daemon that keeps LSP processes alive across invocations (~500ms warm).
  2. Direct mode (--no-daemon): Boots a fresh LSP per invocation (~2-5s cold).

The daemon is auto-spawned on first use — zero configuration needed.
"""

import json
import os
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Platform-aware daemon directory & socket paths
# ---------------------------------------------------------------------------

def get_daemon_dir() -> Path:
    """User-scoped directory for daemon state files (socket, PID, log)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux
        xdg = os.environ.get("XDG_RUNTIME_DIR", "")
        base = Path(xdg) if xdg else (Path.home() / ".local" / "share")
    d = base / "recon"
    d.mkdir(parents=True, exist_ok=True)
    return d


_USE_UNIX_SOCKET: bool = hasattr(socket, "AF_UNIX")


def get_pid_file() -> Path:
    return get_daemon_dir() / "daemon.pid"

def get_port_file() -> Path:
    return get_daemon_dir() / "daemon.port"

def get_sock_file() -> Path:
    return get_daemon_dir() / "daemon.sock"

def get_log_file() -> Path:
    return get_daemon_dir() / "daemon.log"


# ---------------------------------------------------------------------------
# Wire protocol: 4-byte big-endian length prefix + UTF-8 JSON
# ---------------------------------------------------------------------------

_HEADER = struct.Struct(">I")


def _json_default(obj: Any) -> Any:
    import dataclasses
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def send_frame(sock: socket.socket, payload: Any) -> None:
    data = json.dumps(payload, default=_json_default).encode("utf-8")
    sock.sendall(_HEADER.pack(len(data)) + data)


def recv_frame(sock: socket.socket) -> Any:
    header = _recvall(sock, _HEADER.size)
    if not header:
        raise ConnectionResetError("Daemon closed the connection.")
    (length,) = _HEADER.unpack(header)
    data = _recvall(sock, length)
    if not data:
        raise ConnectionResetError("Daemon closed the connection mid-frame.")
    return json.loads(data.decode("utf-8"))


def _recvall(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return b""
        buf.extend(chunk)
    return bytes(buf)


# ---------------------------------------------------------------------------
# Daemon liveness check
# ---------------------------------------------------------------------------

def is_daemon_alive() -> bool:
    """Check if the recon daemon process is running. Cleans stale PID files."""
    pid_file = get_pid_file()
    if not pid_file.exists():
        return False
    try:
        import psutil
        proc = psutil.Process(int(pid_file.read_text().strip()))
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except Exception:
        pass
    try:
        pid_file.unlink()
    except OSError:
        pass
    return False


def try_claim_daemon_pid() -> bool:
    """Atomic PID file claim — only one process wins when racing."""
    try:
        fd = os.open(str(get_pid_file()), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_daemon_pid() -> None:
    try:
        get_pid_file().unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Daemon connection helpers
# ---------------------------------------------------------------------------

SPAWN_TIMEOUT = 60.0
SOCKET_POLL_INTERVAL = 0.1


def connect_to_daemon() -> socket.socket:
    """Return a connected socket to the daemon."""
    if _USE_UNIX_SOCKET:
        sock_path = str(get_sock_file())
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sock_path)
    else:
        port_file = get_port_file()
        if not port_file.exists():
            raise ConnectionRefusedError("Daemon port file not found.")
        port = int(port_file.read_text().strip())
        if port == 0:
            raise ConnectionRefusedError("Daemon port not yet assigned.")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("localhost", port))
    return s


def wait_for_daemon_socket() -> bool:
    """Poll until daemon socket is ready or timeout elapses."""
    deadline = time.monotonic() + SPAWN_TIMEOUT
    while time.monotonic() < deadline:
        try:
            conn = connect_to_daemon()
            conn.close()
            return True
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            time.sleep(SOCKET_POLL_INTERVAL)
    return False


def spawn_daemon() -> None:
    """Launch the recon daemon as a detached background process."""
    subprocess.Popen(
        [sys.executable, "-m", "recon.daemon"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


# ---------------------------------------------------------------------------
# Request dispatch
# ---------------------------------------------------------------------------

def dispatch_request(payload: dict) -> Any:
    """
    Send a request to the daemon and return the decoded result.

    Auto-spawns the daemon on first use if it's not already running.
    """
    for attempt in range(2):
        try:
            conn = connect_to_daemon()
            break
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            if attempt == 0:
                if not is_daemon_alive():
                    spawn_daemon()
                if not wait_for_daemon_socket():
                    raise RuntimeError("Daemon failed to start within the timeout period.")
            else:
                raise RuntimeError("Could not connect to daemon after spawning.")

    try:
        send_frame(conn, payload)
        response = recv_frame(conn)
    finally:
        conn.close()

    if response.get("status") == "error":
        raise RuntimeError(response.get("error", "Unknown daemon error"))

    return response.get("result")


def dispatch_lsp_request(
    cmd: str,
    lang: str,
    repo_path: str,
    no_daemon: bool = False,
    **kwargs: Any,
) -> Any:
    """
    Route an LSP request either through the daemon (default) or directly
    (when --no-daemon is set).
    """
    if no_daemon:
        return _direct_lsp_request(cmd, lang, repo_path, **kwargs)
    return dispatch_request({"cmd": cmd, "lang": lang, "repo_path": repo_path, **kwargs})


def _direct_lsp_request(cmd: str, lang: str, repo_path: str, **kwargs: Any) -> Any:
    """Cold-start path — boots and tears down the LSP every invocation."""
    from multilspy import SyncLanguageServer
    from multilspy.multilspy_config import MultilspyConfig
    from multilspy.multilspy_logger import MultilspyLogger

    config = MultilspyConfig.from_dict({"code_language": lang})
    logger = MultilspyLogger()
    lsp = SyncLanguageServer.create(config, logger, repo_path)
    with lsp.start_server():
        if cmd == "definition":
            return lsp.request_definition(kwargs["file_path"], kwargs["line"], kwargs["col"])
        elif cmd == "references":
            return lsp.request_references(kwargs["file_path"], kwargs["line"], kwargs["col"])
        elif cmd == "hover":
            return lsp.request_hover(kwargs["file_path"], kwargs["line"], kwargs["col"])
        elif cmd == "document_symbols":
            result, _ = lsp.request_document_symbols(kwargs["file_path"])
            return result
        elif cmd == "workspace_symbol":
            return lsp.request_workspace_symbol(kwargs["query"])
        elif cmd == "completions":
            return lsp.request_completions(
                kwargs["file_path"], kwargs["line"], kwargs["col"],
                kwargs.get("allow_incomplete", False),
            )
        else:
            raise ValueError(f"Unknown command: {cmd}")
