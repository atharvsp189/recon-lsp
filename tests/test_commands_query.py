import json
from unittest.mock import MagicMock
from pathlib import Path
import pytest
from typer.testing import CliRunner

from recon.commands.query import (
    app,
    _resolve_env,
    _get_format,
    definition,
    references,
    hover,
    symbols,
    workspace_symbols,
    completions,
    batch,
)
import recon.commands.query as query_mod


def test_resolve_env_explicit(tmp_path):
    lang, repo = _resolve_env("python", str(tmp_path))
    assert lang == "python"
    assert repo == str(tmp_path.resolve())


def test_resolve_env_file_extensions(tmp_path):
    ext_cases = [
        ("test.py", "python"),
        ("main.rs", "rust"),
        ("app.go", "go"),
        ("index.ts", "typescript"),
        ("script.js", "javascript"),
        ("Main.java", "java"),
        ("Prog.cs", "csharp"),
        ("util.cpp", "cpp"),
        ("code.c", "cpp"),
        ("header.h", "cpp"),
        ("header.hpp", "cpp"),
        ("app.rb", "ruby"),
        ("main.dart", "dart"),
        ("index.php", "php"),
        ("lib.ex", "elixir"),
        ("mix.exs", "elixir"),
        ("App.kt", "kotlin"),
    ]
    for filename, expected_lang in ext_cases:
        lang, repo = _resolve_env(None, str(tmp_path), file_path=filename)
        assert lang == expected_lang


def test_resolve_env_missing_language_raises_exit(runner):
    import typer

    with pytest.raises(typer.Exit) as exc_info:
        _resolve_env(None, None, file_path="unknown.xyz")
    assert exc_info.value.exit_code == 1


def test_get_format():
    assert _get_format(human=True, table=False) == "human"
    assert _get_format(human=False, table=True) == "table"
    assert _get_format(human=False, table=False, cfg_fmt="json") == "json"
    assert _get_format(human=False, table=False, cfg_fmt="custom") == "custom"


def test_definition_command(runner, temp_repo, monkeypatch):
    mock_dispatch = MagicMock(
        return_value=[
            {
                "name": "calculate_sum",
                "location": {
                    "absolutePath": str(temp_repo / "main.py"),
                    "range": {
                        "start": {"line": 3, "character": 4},
                        "end": {"line": 3, "character": 17},
                    },
                },
            }
        ]
    )
    monkeypatch.setattr("recon.commands.query.dispatch_lsp_request", mock_dispatch)

    res = runner.invoke(
        app,
        [
            "definition",
            "-f",
            "main.py",
            "-L",
            "4",
            "-s",
            "calculate_sum",
            "-r",
            str(temp_repo),
            "-l",
            "python",
            "--context",
            "1",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert len(data) == 1
    assert "context" in data[0]


def test_definition_command_error(runner, temp_repo, monkeypatch):
    monkeypatch.setattr(
        "recon.commands.query.dispatch_lsp_request",
        MagicMock(side_effect=Exception("LSP failed")),
    )
    res = runner.invoke(
        app,
        [
            "definition",
            "-f",
            "main.py",
            "-L",
            "4",
            "-s",
            "calculate_sum",
            "-r",
            str(temp_repo),
            "-l",
            "python",
        ],
    )
    assert res.exit_code == 1
    assert "LSP failed" in res.output


def test_references_command(runner, temp_repo, monkeypatch):
    mock_dispatch = MagicMock(
        return_value=[
            {
                "name": "calculate_sum",
                "location": {
                    "absolutePath": str(temp_repo / "main.py"),
                    "range": {
                        "start": {"line": 3, "character": 4},
                        "end": {"line": 3, "character": 17},
                    },
                },
            }
        ]
    )
    monkeypatch.setattr("recon.commands.query.dispatch_lsp_request", mock_dispatch)

    res = runner.invoke(
        app,
        [
            "references",
            "-f",
            "main.py",
            "-L",
            "4",
            "-c",
            "4",
            "-r",
            str(temp_repo),
            "-l",
            "python",
            "-H",
        ],
    )
    assert res.exit_code == 0
    assert "main.py:4" in res.output


def test_references_command_error(runner, temp_repo, monkeypatch):
    monkeypatch.setattr(
        "recon.commands.query.dispatch_lsp_request",
        MagicMock(side_effect=Exception("Ref failed")),
    )
    res = runner.invoke(
        app,
        [
            "references",
            "-f",
            "main.py",
            "-L",
            "4",
            "-c",
            "4",
            "-r",
            str(temp_repo),
            "-l",
            "python",
        ],
    )
    assert res.exit_code == 1
    assert "Ref failed" in res.output


def test_hover_command(runner, temp_repo, monkeypatch):
    mock_dispatch = MagicMock(return_value={"contents": "Function calculate_sum(a, b)"})
    monkeypatch.setattr("recon.commands.query.dispatch_lsp_request", mock_dispatch)

    res = runner.invoke(
        app,
        [
            "hover",
            "-f",
            "main.py",
            "-L",
            "4",
            "-s",
            "calculate_sum",
            "-r",
            str(temp_repo),
            "-l",
            "python",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["contents"] == "Function calculate_sum(a, b)"


def test_hover_command_error(runner, temp_repo, monkeypatch):
    monkeypatch.setattr(
        "recon.commands.query.dispatch_lsp_request",
        MagicMock(side_effect=Exception("Hover failed")),
    )
    res = runner.invoke(
        app,
        [
            "hover",
            "-f",
            "main.py",
            "-L",
            "4",
            "-c",
            "4",
            "-r",
            str(temp_repo),
            "-l",
            "python",
        ],
    )
    assert res.exit_code == 1
    assert "Hover failed" in res.output


def test_symbols_command(runner, temp_repo, monkeypatch):
    raw_symbols = [
        {
            "name": "calculate_sum",
            "kind": 12,
            "range": {"start": {"line": 3}},
        },  # Function
        {"name": "result", "kind": 13, "range": {"start": {"line": 4}}},  # Variable
        {"name": "Calculator", "kind": 5, "range": {"start": {"line": 7}}},  # Class
    ]
    mock_dispatch = MagicMock(return_value=raw_symbols)
    monkeypatch.setattr("recon.commands.query.dispatch_lsp_request", mock_dispatch)

    # Without declarations_only filter
    res = runner.invoke(
        app,
        [
            "symbols",
            "-f",
            "main.py",
            "-r",
            str(temp_repo),
            "-l",
            "python",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert len(data) == 3
    assert data[0]["location"]["relativePath"] == "main.py"

    # With declarations_only filter (removes Variable with kind 13)
    res_filtered = runner.invoke(
        app,
        [
            "symbols",
            "-f",
            "main.py",
            "-r",
            str(temp_repo),
            "-l",
            "python",
            "--declarations-only",
        ],
    )
    assert res_filtered.exit_code == 0
    data_filtered = json.loads(res_filtered.output)
    assert len(data_filtered) == 2
    assert all(item["name"] != "result" for item in data_filtered)


def test_symbols_command_error(runner, temp_repo, monkeypatch):
    monkeypatch.setattr(
        "recon.commands.query.dispatch_lsp_request",
        MagicMock(side_effect=Exception("Syms failed")),
    )
    res = runner.invoke(
        app,
        [
            "symbols",
            "-f",
            "main.py",
            "-r",
            str(temp_repo),
            "-l",
            "python",
        ],
    )
    assert res.exit_code == 1
    assert "Syms failed" in res.output


def test_workspace_symbols_command(runner, temp_repo, monkeypatch):
    mock_dispatch = MagicMock(
        return_value=[
            {
                "name": "Calculator",
                "location": {
                    "absolutePath": str(temp_repo / "main.py"),
                    "range": {
                        "start": {"line": 7, "character": 6},
                        "end": {"line": 7, "character": 16},
                    },
                },
            }
        ]
    )
    monkeypatch.setattr("recon.commands.query.dispatch_lsp_request", mock_dispatch)

    res = runner.invoke(
        app,
        [
            "workspace-symbols",
            "-q",
            "Calculator",
            "-r",
            str(temp_repo),
            "-l",
            "python",
            "-T",
        ],
    )
    assert res.exit_code == 0
    assert "Calculator" in res.output


def test_workspace_symbols_command_error(runner, temp_repo, monkeypatch):
    monkeypatch.setattr(
        "recon.commands.query.dispatch_lsp_request",
        MagicMock(side_effect=Exception("WS failed")),
    )
    res = runner.invoke(
        app,
        [
            "workspace-symbols",
            "-q",
            "Calc",
            "-r",
            str(temp_repo),
            "-l",
            "python",
        ],
    )
    assert res.exit_code == 1
    assert "WS failed" in res.output


def test_completions_command(runner, temp_repo, monkeypatch):
    mock_dispatch = MagicMock(return_value=[{"label": "calculate_sum", "kind": 3}])
    monkeypatch.setattr("recon.commands.query.dispatch_lsp_request", mock_dispatch)

    res = runner.invoke(
        app,
        [
            "completions",
            "-f",
            "main.py",
            "-L",
            "4",
            "-c",
            "5",
            "-r",
            str(temp_repo),
            "-l",
            "python",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert len(data) == 1
    assert data[0]["label"] == "calculate_sum"


def test_completions_command_error(runner, temp_repo, monkeypatch):
    monkeypatch.setattr(
        "recon.commands.query.dispatch_lsp_request",
        MagicMock(side_effect=Exception("Comp failed")),
    )
    res = runner.invoke(
        app,
        [
            "completions",
            "-f",
            "main.py",
            "-L",
            "4",
            "-c",
            "5",
            "-r",
            str(temp_repo),
            "-l",
            "python",
        ],
    )
    assert res.exit_code == 1
    assert "Comp failed" in res.output


def test_batch_dry_run(runner, tmp_path):
    batch_file = tmp_path / "queries.json"
    queries = [
        {
            "command": "definition",
            "file_path": "main.py",
            "line": 4,
            "symbol": "calculate_sum",
        },
        {"command": "hover", "file_path": "main.py", "line": 8, "symbol": "Calculator"},
    ]
    batch_file.write_text(json.dumps(queries), encoding="utf-8")

    res = runner.invoke(app, ["batch", "-f", str(batch_file), "--dry-run"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert len(data) == 2


def test_batch_invalid_json(runner, tmp_path):
    batch_file = tmp_path / "invalid.json"
    batch_file.write_text("{not a list}", encoding="utf-8")

    res = runner.invoke(app, ["batch", "-f", str(batch_file)])
    assert res.exit_code == 1
    assert "JSONDecodeError" in res.output or "Expecting" in res.output


def test_batch_non_list_json(runner, tmp_path):
    batch_file = tmp_path / "dict.json"
    batch_file.write_text(json.dumps({"command": "definition"}), encoding="utf-8")

    res = runner.invoke(app, ["batch", "-f", str(batch_file)])
    assert res.exit_code == 1
    assert "JSON file must contain an array of query objects" in res.output


def test_batch_execution_all_types(runner, temp_repo, monkeypatch):
    mock_dispatch = MagicMock(return_value=[{"result": "ok"}])
    monkeypatch.setattr("recon.commands.query.dispatch_lsp_request", mock_dispatch)

    batch_file = temp_repo / "all_queries.json"
    queries = [
        # 1. Missing command field
        {"file_path": "main.py"},
        # 2. Missing env resolution (no lang, unknown extension)
        {"command": "definition", "file_path": "file.xyz", "repo_path": None},
        # 3. Definition command
        {
            "command": "definition",
            "file_path": "main.py",
            "line": 4,
            "symbol": "calculate_sum",
            "lang": "python",
            "repo_path": str(temp_repo),
        },
        # 4. References command
        {
            "command": "references",
            "file_path": "main.py",
            "line": 4,
            "symbol": "calculate_sum",
            "lang": "python",
            "repo_path": str(temp_repo),
        },
        # 5. Hover command
        {
            "command": "hover",
            "file_path": "main.py",
            "line": 4,
            "symbol": "calculate_sum",
            "lang": "python",
            "repo_path": str(temp_repo),
        },
        # 6. Completions command
        {
            "command": "completions",
            "file_path": "main.py",
            "line": 4,
            "symbol": "calculate_sum",
            "lang": "python",
            "repo_path": str(temp_repo),
        },
        # 7. Symbols command
        {
            "command": "symbols",
            "file_path": "main.py",
            "lang": "python",
            "repo_path": str(temp_repo),
        },
        # 8. Workspace-symbols command
        {
            "command": "workspace-symbols",
            "query": "Calc",
            "lang": "python",
            "repo_path": str(temp_repo),
        },
        # 9. Unknown command
        {
            "command": "invalid_cmd",
            "file_path": "main.py",
            "lang": "python",
            "repo_path": str(temp_repo),
        },
        # 10. Missing line field for definition
        {
            "command": "definition",
            "file_path": "main.py",
            "lang": "python",
            "repo_path": str(temp_repo),
        },
    ]
    batch_file.write_text(json.dumps(queries), encoding="utf-8")

    # JSON mode
    res = runner.invoke(app, ["batch", "-f", str(batch_file), "--context", "1"])
    assert res.exit_code == 0
    json_start = res.output.find("{")
    envelope = json.loads(res.output[json_start:])
    assert envelope["total"] == 10
    assert envelope["succeeded"] == 6
    assert envelope["failed"] == 4
    assert len(envelope["results"]) == 10

    # Human mode
    res_human = runner.invoke(app, ["batch", "-f", str(batch_file), "-H"])
    assert res_human.exit_code == 0
    assert "Batch completed in" in res_human.output
