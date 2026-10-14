import asyncio
import os
import sys
import threading
from unittest.mock import MagicMock
import pytest

import recon
from recon import _patched_start_server


def test_version_string():
    assert isinstance(recon.__version__, str)
    assert len(recon.__version__.split(".")) >= 2


def test_path_injection(monkeypatch):
    test_bin = "/fake/custom/bin"
    test_exe = "/fake/custom/exe"
    current_path = "/usr/bin:/bin"

    paths_to_add = []
    if test_bin not in current_path:
        paths_to_add.append(test_bin)
    if test_exe not in current_path:
        paths_to_add.append(test_exe)

    new_path = os.pathsep.join(paths_to_add + [current_path])
    assert test_bin in new_path
    assert test_exe in new_path


def test_patched_start_server_success():
    class DummyLangServer:
        def __init__(self):
            self.completions_available = threading.Event()

        def start_server(self):
            class DummyCtx:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return None

            return DummyCtx()

    class DummySyncServer:
        def __init__(self):
            self.language_server = DummyLangServer()
            self.timeout = 5

    sync_server = DummySyncServer()

    with _patched_start_server(sync_server) as server:
        assert server is sync_server
        assert sync_server.language_server.completions_available.wait(timeout=1.0)


def test_patched_start_server_exception_on_enter():
    class FailingLangServer:
        def start_server(self):
            class FailingCtx:
                async def __aenter__(self):
                    raise ValueError("Connection aborted")

                async def __aexit__(self, exc_type, exc, tb):
                    return None

            return FailingCtx()

    class DummySyncServer:
        def __init__(self):
            self.language_server = FailingLangServer()
            self.timeout = 2

    sync_server = DummySyncServer()

    with pytest.raises(RuntimeError, match="LSP server failed to start or timed out"):
        with _patched_start_server(sync_server):
            pass


def test_patched_start_server_exception_on_exit():
    class FailingExitLangServer:
        def start_server(self):
            class FailingExitCtx:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    raise RuntimeError("Exit error")

            return FailingExitCtx()

    class DummySyncServer:
        def __init__(self):
            self.language_server = FailingExitLangServer()
            self.timeout = 5

    sync_server = DummySyncServer()

    # The exception on exit is suppressed in finally block
    with _patched_start_server(sync_server):
        pass
