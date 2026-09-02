"""
daemon.py — The recon background daemon server.

Run via:  python -m recon.daemon
Or via:   recon daemon start  (which launches this as a subprocess)

Architecture:
    - One daemon per user, managing N LSP instances (one per lang+repo pair).
    - Uses contextlib.ExitStack to keep SyncLanguageServer contexts alive.
    - Thread-per-connection model; each LSP instance serialized via its own lock.
    - Auto-shuts-down after IDLE_TIMEOUT_SECONDS of inactivity.
    - Handles SIGTERM and atexit for graceful cleanup.
"""

import atexit
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Dict, Tuple

from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger

from recon.lsp.client import (
    _USE_UNIX_SOCKET,
    get_daemon_dir,
    get_pid_file,
    get_port_file,
    get_sock_file,
    get_log_file,
    release_daemon_pid,
    send_frame,
    recv_frame,
    try_claim_daemon_pid,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

IDLE_TIMEOUT_SECONDS = 15 * 60  # 15 minutes
LSP_REQUEST_TIMEOUT = 30        # seconds per LSP call
DAEMON_LOG_FILE = get_log_file()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    filename=str(DAEMON_LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("recon.daemon")


# ---------------------------------------------------------------------------
# LSP Instance Cache
# ---------------------------------------------------------------------------

class LspEntry:
    """Wraps a live SyncLanguageServer kept alive via ExitStack."""

    def __init__(self, lsp: SyncLanguageServer, exit_stack: ExitStack) -> None:
        self.lsp = lsp
        self._exit_stack = exit_stack
        self._lock = threading.Lock()

    def execute(self, cmd: str, **kwargs: Any) -> Any:
        with self._lock:
            return _dispatch_lsp_cmd(self.lsp, cmd, **kwargs)

    def stop(self) -> None:
        try:
            self._exit_stack.close()
        except Exception as e:
            log.warning("Error stopping LSP: %s", e)


def _dispatch_lsp_cmd(lsp: SyncLanguageServer, cmd: str, **kwargs: Any) -> Any:
    """Route a command string to the appropriate SyncLanguageServer method."""
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
        raise ValueError(f"Unknown LSP command: {cmd!r}")


# Global LSP cache: (lang, repo_path) -> LspEntry
_lsp_cache: Dict[Tuple[str, str], LspEntry] = {}
_cache_lock = threading.Lock()

_last_request_time: float = time.monotonic()
_shutdown_event = threading.Event()


def get_or_create_lsp(lang: str, repo_path: str) -> LspEntry:
    """Return an existing warm LSP entry or boot a new one."""
    key = (lang, repo_path)
    with _cache_lock:
        if key in _lsp_cache:
            return _lsp_cache[key]

        log.info("Booting LSP: lang=%s repo=%s", lang, repo_path)
        config = MultilspyConfig.from_dict({"code_language": lang})
        logger = MultilspyLogger()
        lsp = SyncLanguageServer.create(
            config, logger, str(Path(repo_path).absolute()),
            timeout=LSP_REQUEST_TIMEOUT,
        )

        stack = ExitStack()
        stack.enter_context(lsp.start_server())

        entry = LspEntry(lsp, stack)
        _lsp_cache[key] = entry
        log.info("LSP ready: lang=%s", lang)
        return entry


# ---------------------------------------------------------------------------
# Connection handler
# ---------------------------------------------------------------------------

def handle_connection(conn: socket.socket) -> None:
    """Handle a single client connection: receive one request, send one response."""
    global _last_request_time
    try:
        payload = recv_frame(conn)
        _last_request_time = time.monotonic()

        cmd = payload.get("cmd", "")
        log.info("Request: cmd=%s lang=%s", cmd, payload.get("lang"))

        # --- Internal control commands ---
        if cmd == "ping":
            send_frame(conn, {"status": "ok", "result": "pong"})
            return

        if cmd == "stop":
            send_frame(conn, {"status": "ok", "result": "daemon shutting down"})
            _shutdown_event.set()
            return

        if cmd == "status":
            with _cache_lock:
                cached = [{"lang": k[0], "repo_path": k[1]} for k in _lsp_cache]
            send_frame(conn, {"status": "ok", "result": {"cached_lsps": cached}})
            return

        # --- LSP commands ---
        lang = payload.get("lang")
        repo_path = payload.get("repo_path")
        if not lang or not repo_path:
            send_frame(conn, {"status": "error", "error": "Missing 'lang' or 'repo_path' in request."})
            return

        try:
            entry = get_or_create_lsp(lang, repo_path)
        except Exception as e:
            log.exception("Error booting LSP")
            send_frame(conn, {"status": "setup_error", "lang": lang, "error": str(e)})
            return

        lsp_kwargs = {k: v for k, v in payload.items() if k not in ("cmd", "lang", "repo_path")}
        result = entry.execute(cmd, **lsp_kwargs)
        send_frame(conn, {"status": "ok", "result": result})

    except Exception as e:
        log.exception("Error handling request")
        try:
            send_frame(conn, {"status": "error", "error": str(e)})
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Idle watchdog
# ---------------------------------------------------------------------------

def _idle_watchdog() -> None:
    while not _shutdown_event.is_set():
        elapsed = time.monotonic() - _last_request_time
        remaining = IDLE_TIMEOUT_SECONDS - elapsed
        if remaining <= 0:
            log.info("Idle timeout reached. Shutting down daemon.")
            _shutdown_event.set()
            return
        _shutdown_event.wait(timeout=min(remaining, 30))


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def _cleanup() -> None:
    log.info("Cleaning up daemon resources.")
    with _cache_lock:
        for key, entry in list(_lsp_cache.items()):
            log.info("Stopping LSP: lang=%s repo=%s", key[0], key[1])
            entry.stop()
        _lsp_cache.clear()

    release_daemon_pid()

    if _USE_UNIX_SOCKET:
        try:
            get_sock_file().unlink()
        except OSError:
            pass
    else:
        try:
            get_port_file().unlink()
        except OSError:
            pass

    log.info("Daemon exited cleanly.")


atexit.register(_cleanup)


def _handle_sigterm(signum: int, frame: Any) -> None:
    log.info("Received SIGTERM.")
    _shutdown_event.set()


# ---------------------------------------------------------------------------
# Main server loop
# ---------------------------------------------------------------------------

def run_daemon() -> None:
    """
    Entry point for the daemon process.

    1. Atomically claims the PID file.
    2. Binds a socket (AF_UNIX or TCP fallback).
    3. Starts the idle watchdog thread.
    4. Accepts connections, spawning a thread per connection.
    5. On shutdown signal, cleans up via atexit.
    """
    if not try_claim_daemon_pid():
        log.info("Another daemon process is already running. Exiting.")
        sys.exit(0)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_sigterm)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    if _USE_UNIX_SOCKET:
        sock_path = str(get_sock_file())
        try:
            os.unlink(sock_path)
        except OSError:
            pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(sock_path)
        log.info("Listening on Unix socket: %s", sock_path)
    else:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("localhost", 0))
        port = server.getsockname()[1]
        get_port_file().write_text(str(port))
        log.info("Listening on TCP localhost:%d", port)

    server.listen(16)
    server.settimeout(2.0)

    log.info("Daemon PID=%d started.", os.getpid())

    watchdog = threading.Thread(target=_idle_watchdog, daemon=True, name="idle-watchdog")
    watchdog.start()

    while not _shutdown_event.is_set():
        try:
            conn, _ = server.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        t = threading.Thread(target=handle_connection, args=(conn,), daemon=True)
        t.start()

    server.close()


if __name__ == "__main__":
    run_daemon()
