"""
recon — LSP-powered code reconnaissance CLI.

Semantic code intelligence for AI agents and humans,
built on top of multilspy.
"""

__version__ = "0.1.0"

import os
import sys
import asyncio
import threading
from contextlib import contextmanager
from pathlib import Path

# Inject virtualenv bin paths into PATH for multilspy LSP discovery
_bin_path = str(Path(sys.prefix) / "bin")
_exe_dir = str(Path(sys.executable).parent)
_current_path = os.environ.get("PATH", "")
_paths_to_add = []
if _bin_path not in _current_path:
    _paths_to_add.append(_bin_path)
if _exe_dir not in _current_path and _exe_dir != _bin_path:
    _paths_to_add.append(_exe_dir)
if _paths_to_add:
    os.environ["PATH"] = os.pathsep.join(_paths_to_add + [_current_path])


# Monkeypatch SyncLanguageServer to add initialization timeouts and prevent completion deadlocks
try:
    from multilspy import SyncLanguageServer

    @contextmanager
    def _patched_start_server(self):
        self.loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        loop_thread.start()
        ctx = self.language_server.start_server()
        try:
            # Enforce initialization timeout
            timeout_val = getattr(self, "timeout", None) or 15
            future = asyncio.run_coroutine_threadsafe(ctx.__aenter__(), loop=self.loop)
            future.result(timeout=timeout_val)
            
            # Immediately unlock completions event to prevent deadlock
            if hasattr(self.language_server, "completions_available"):
                self.loop.call_soon_threadsafe(self.language_server.completions_available.set)
                
        except Exception as e:
            self.loop.call_soon_threadsafe(self.loop.stop)
            loop_thread.join()
            raise RuntimeError(f"LSP server failed to start or timed out: {e}")
            
        try:
            yield self
        finally:
            try:
                asyncio.run_coroutine_threadsafe(
                    ctx.__aexit__(None, None, None), loop=self.loop
                ).result(timeout=5)
            except Exception:
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)
            loop_thread.join()

    SyncLanguageServer.start_server = _patched_start_server
except ImportError:
    pass
