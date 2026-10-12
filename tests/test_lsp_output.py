import json
import pytest

from recon.lsp.output import (
    print_json,
    print_human,
    print_table,
    print_output,
    print_error,
    print_success,
    print_info,
)

def test_print_json(capsys):
    data = {"key": "value", "count": 10}
    print_json(data)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed == data

def test_print_human_with_locations_and_context(capsys):
    data = [
        {
            "name": "calculate_sum",
            "location": {
                "relativePath": "src/calc.py",
                "range": {"start": {"line": 10}},
                "context": "def calculate_sum():\n    return 0",
            },
        },
        {
            # Test URI fallback when path is missing
            "location": {
                "uri": "file:///path/to/other.py",
                "range": {"start": {"line": 5}},
            },
        },
        {
            # Test unknown path and no start line
            "range": {},
        },
    ]
    print_human(data)
    captured = capsys.readouterr()
    assert "src/calc.py:11" in captured.out
    assert "calculate_sum" in captured.out
    assert "other.py:6" in captured.out
    assert "unknown:?" in captured.out

def test_print_human_list_non_locations(capsys):
    data = [{"raw_field": 123}, {"another": True}]
    print_human(data)
    captured = capsys.readouterr()
    assert "raw_field" in captured.out
    assert "123" in captured.out

def test_print_human_dict_and_string(capsys):
    dict_data = {"Language": "python", "Daemon": "running"}
    print_human(dict_data)
    captured = capsys.readouterr()
    assert "Language: python" in captured.out
    assert "Daemon: running" in captured.out

    print_human("Simple text message")
    captured = capsys.readouterr()
    assert "Simple text message" in captured.out

def test_print_human_fallback_primitive(capsys):
    print_human(12345)
    captured = capsys.readouterr()
    assert "12345" in captured.out

def test_print_table_empty_or_non_list(capsys):
    print_table([])
    captured = capsys.readouterr()
    assert "[]" in captured.out

    print_table({"not": "a list"})
    captured = capsys.readouterr()
    assert '"not": "a list"' in captured.out

def test_print_table_list_of_dicts(capsys):
    data = [
        {
            "name": "foo",
            "kind": "function",
            "context": "should be omitted from columns",
            "extra": {"nested": 1},
            "none_val": None,
        },
        {
            "name": "bar",
            "kind": "class",
            "context_error": "also omitted",
            "extra": None,
            "none_val": "not null",
        },
    ]
    print_table(data, title="Symbol Table")
    captured = capsys.readouterr()
    assert "Symbol Table" in captured.out
    assert "foo" in captured.out
    assert "function" in captured.out
    assert "should be omitted from columns" not in captured.out

def test_print_table_list_of_primitives(capsys):
    data = ["item 1", "item 2", "item 3"]
    print_table(data, title="Simple List")
    captured = capsys.readouterr()
    assert "item 1" in captured.out
    assert "item 2" in captured.out

def test_print_output_dispatch(monkeypatch):
    calls = []
    monkeypatch.setattr("recon.lsp.output.print_human", lambda d: calls.append(("human", d)))
    monkeypatch.setattr("recon.lsp.output.print_table", lambda d, title: calls.append(("table", d, title)))
    monkeypatch.setattr("recon.lsp.output.print_json", lambda d: calls.append(("json", d)))

    print_output({"test": 1}, fmt="human")
    assert calls[-1] == ("human", {"test": 1})

    print_output({"test": 2}, fmt="table", title="MyTable")
    assert calls[-1] == ("table", {"test": 2}, "MyTable")

    print_output({"test": 3}, fmt="json")
    assert calls[-1] == ("json", {"test": 3})

    print_output({"test": 4}, fmt="unknown_fallback")
    assert calls[-1] == ("json", {"test": 4})

def test_print_status_helpers(capsys):
    print_error("Failed to connect")
    captured = capsys.readouterr()
    assert "Error:" in captured.out
    assert "Failed to connect" in captured.out

    print_success("Operation completed")
    captured = capsys.readouterr()
    assert "Operation completed" in captured.out

    print_info("Status update")
    captured = capsys.readouterr()
    assert "Status update" in captured.out
