import dataclasses
import json
import os
import pytest
from pathlib import Path

from recon.utils import (
    ReconJSONEncoder,
    resolve_column,
    uri_to_path,
    add_context_to_locations,
)

@dataclasses.dataclass
class DummyLocation:
    name: str
    line: int

class UnserializableObj:
    pass

def test_recon_json_encoder():
    loc = DummyLocation(name="foo", line=42)
    encoded = json.dumps({"loc": loc}, cls=ReconJSONEncoder)
    data = json.loads(encoded)
    assert data["loc"] == {"name": "foo", "line": 42}

    # Should raise TypeError for objects that are neither dataclasses nor JSON serializable
    with pytest.raises(TypeError):
        json.dumps(UnserializableObj(), cls=ReconJSONEncoder)

def test_resolve_column_explicit():
    line, col = resolve_column("/fake/repo", "fake.py", line=10, column=5, symbol=None)
    assert line == 10
    assert col == 5

def test_resolve_column_missing_both():
    with pytest.raises(ValueError, match="You must provide either --column or --symbol"):
        resolve_column("/fake/repo", "fake.py", line=10, column=None, symbol=None)

def test_resolve_column_exact(temp_repo):
    # main.py has `def calculate_sum(a, b):` on 0-indexed line 3
    line, col = resolve_column(str(temp_repo), "main.py", line=3, column=None, symbol="calculate_sum")
    assert line == 3
    assert col == 4

def test_resolve_column_fuzzy_search(temp_repo):
    # Search for calculate_sum which is on line 3, but provide line=4 (offset -1)
    line, col = resolve_column(str(temp_repo), "main.py", line=4, column=None, symbol="calculate_sum")
    assert line == 3
    assert col == 4

    # Provide line=2 (offset +1)
    line, col = resolve_column(str(temp_repo), "main.py", line=2, column=None, symbol="calculate_sum")
    assert line == 3
    assert col == 4

    # Provide line=5 (offset -2)
    line, col = resolve_column(str(temp_repo), "main.py", line=5, column=None, symbol="calculate_sum")
    assert line == 3
    assert col == 4

    # Provide line=1 (offset +2)
    line, col = resolve_column(str(temp_repo), "main.py", line=1, column=None, symbol="calculate_sum")
    assert line == 3
    assert col == 4

def test_resolve_column_symbol_not_found(temp_repo):
    with pytest.raises(ValueError, match="Symbol 'nonexistent' not found on or around line 4"):
        resolve_column(str(temp_repo), "main.py", line=3, column=None, symbol="nonexistent")

def test_resolve_column_file_read_error(temp_repo):
    with pytest.raises(ValueError, match="Error reading file to resolve symbol"):
        resolve_column(str(temp_repo), "missing.py", line=3, column=None, symbol="foo")

def test_uri_to_path():
    # Normal file URI
    uri = "file:///tmp/test/repo/main.py"
    res = uri_to_path(uri)
    assert isinstance(res, str)
    assert "main.py" in res

def test_uri_to_path_relpath_value_error(monkeypatch):
    # Simulate os.path.relpath raising ValueError (e.g. cross-drive on Windows)
    def fake_relpath(path):
        raise ValueError("Cannot specify relative path between different drives")
    monkeypatch.setattr(os.path, "relpath", fake_relpath)
    res = uri_to_path("file:///C:/Users/test/file.py")
    assert "file.py" in res

def test_add_context_to_locations_zero_or_negative(temp_repo):
    locs = [{"name": "test"}]
    assert add_context_to_locations(locs, 0) == locs
    assert add_context_to_locations(locs, -1) == locs

def test_add_context_to_locations_with_absolute_path(temp_repo):
    src_file = temp_repo / "main.py"
    locations = [
        {
            "name": "calc",
            "location": {
                "absolutePath": str(src_file),
                "range": {
                    "start": {"line": 3, "character": 4},
                    "end": {"line": 5, "character": 17},
                },
            },
        }
    ]
    enriched = add_context_to_locations(locations, context_lines=1)
    assert "context" in enriched[0]
    ctx = enriched[0]["context"]
    assert "def calculate_sum" in ctx
    assert "result = a + b" in ctx
    assert "return result" in ctx

def test_add_context_to_locations_with_uri(temp_repo):
    src_file = temp_repo / "main.py"
    uri = src_file.as_uri()
    locations = [
        {
            "name": "Calculator",
            "uri": uri,
            "range": {
                "start": {"line": 7, "character": 6},
                "end": {"line": 7, "character": 16},
            },
        }
    ]
    enriched = add_context_to_locations(locations, context_lines=2)
    assert "context" in enriched[0]
    assert "class Calculator:" in enriched[0]["context"]

def test_add_context_to_locations_file_error():
    locations = [
        {
            "location": {
                "absolutePath": "/nonexistent/path/code.py",
                "range": {
                    "start": {"line": 1, "character": 0},
                    "end": {"line": 2, "character": 0},
                },
            }
        }
    ]
    enriched = add_context_to_locations(locations, context_lines=2)
    assert "context_error" in enriched[0]
    assert "No such file or directory" in enriched[0]["context_error"]

def test_add_context_to_locations_missing_range_or_path():
    locations = [{"other": 123}]
    enriched = add_context_to_locations(locations, context_lines=2)
    assert "context" not in enriched[0]
    assert "context_error" not in enriched[0]
