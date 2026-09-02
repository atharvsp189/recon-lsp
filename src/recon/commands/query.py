"""
query.py — All LSP query commands for recon.

Commands:
  - definition       — Go-to-definition
  - references       — Find all references
  - hover            — Hover info (types, docs, signatures)
  - symbols          — Document symbols (file-level)
  - workspace-symbols — Workspace-wide symbol search
  - completions      — Autocompletions at a point
"""

import json
import typer
from pathlib import Path
from typing import Optional

from recon.config import load_config
from recon.lsp.client import dispatch_lsp_request
from recon.lsp.output import print_output, print_error
from recon.utils import resolve_column, add_context_to_locations

app = typer.Typer(help="LSP query commands for semantic code intelligence.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_env(
    lang: Optional[str],
    repo_path: Optional[str],
    file_path: Optional[str] = None,
) -> tuple[str, str]:
    """Resolve language and repo_path from CLI flags or config."""
    cfg = load_config(repo_path)
    final_lang = lang or cfg.language
    final_repo = repo_path or cfg.repo_path

    if not final_lang and file_path:
        ext = Path(file_path).suffix.lower()
        ext_map = {
            ".py": "python", ".rs": "rust", ".go": "go",
            ".ts": "typescript", ".js": "javascript",
            ".java": "java", ".cs": "csharp",
            ".cpp": "cpp", ".c": "cpp", ".h": "cpp", ".hpp": "cpp",
            ".rb": "ruby", ".dart": "dart", ".php": "php",
            ".ex": "elixir", ".exs": "elixir", ".kt": "kotlin"
        }
        final_lang = ext_map.get(ext)

    if not final_lang:
        print_error("Missing --lang and no default set. Run 'recon init' first.")
        raise typer.Exit(code=1)
    if not final_repo:
        final_repo = "."

    return final_lang, str(Path(final_repo).resolve())


def _get_format(human: bool, table: bool, cfg_fmt: str = "json") -> str:
    if human:
        return "human"
    if table:
        return "table"
    return cfg_fmt


# ---------------------------------------------------------------------------
# definition
# ---------------------------------------------------------------------------

@app.command()
def definition(
    file_path: str = typer.Option(..., "--file-path", "-f", help="Relative path to the file"),
    line: int = typer.Option(..., "--line", "-L", help="Line number (1-indexed)"),
    column: Optional[int] = typer.Option(None, "--column", "-c", help="Column number (0-indexed)"),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Symbol string (auto-calculates column)"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Programming language"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", "-r", help="Repository root path"),
    context_lines: int = typer.Option(0, "--context", help="Surrounding lines to include"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-readable output"),
    table: bool = typer.Option(False, "--table", "-T", help="Table output"),
    no_daemon: bool = typer.Option(False, "--no-daemon", help="Bypass daemon, boot fresh LSP"),
):
    """Find the definition of a symbol at the given location."""
    try:
        lang_r, repo_r = _resolve_env(lang, repo_path, file_path)
        line_0 = line - 1
        line_0, col = resolve_column(repo_r, file_path, line_0, column, symbol)
        res = dispatch_lsp_request("definition", lang_r, repo_r, no_daemon, file_path=file_path, line=line_0, col=col)
        res = add_context_to_locations(res or [], context_lines)
        fmt = _get_format(human, table)
        print_output(res, fmt, title="Definition")
    except typer.Exit:
        raise
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# references
# ---------------------------------------------------------------------------

@app.command()
def references(
    file_path: str = typer.Option(..., "--file-path", "-f", help="Relative path to the file"),
    line: int = typer.Option(..., "--line", "-L", help="Line number (1-indexed)"),
    column: Optional[int] = typer.Option(None, "--column", "-c", help="Column number (0-indexed)"),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Symbol string (auto-calculates column)"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Programming language"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", "-r", help="Repository root path"),
    context_lines: int = typer.Option(0, "--context", help="Surrounding lines to include"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-readable output"),
    table: bool = typer.Option(False, "--table", "-T", help="Table output"),
    no_daemon: bool = typer.Option(False, "--no-daemon", help="Bypass daemon, boot fresh LSP"),
):
    """Find all references to a symbol at the given location."""
    try:
        lang_r, repo_r = _resolve_env(lang, repo_path, file_path)
        line_0 = line - 1
        line_0, col = resolve_column(repo_r, file_path, line_0, column, symbol)
        res = dispatch_lsp_request("references", lang_r, repo_r, no_daemon, file_path=file_path, line=line_0, col=col)
        res = add_context_to_locations(res or [], context_lines)
        fmt = _get_format(human, table)
        print_output(res, fmt, title="References")
    except typer.Exit:
        raise
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# hover
# ---------------------------------------------------------------------------

@app.command()
def hover(
    file_path: str = typer.Option(..., "--file-path", "-f", help="Relative path to the file"),
    line: int = typer.Option(..., "--line", "-L", help="Line number (1-indexed)"),
    column: Optional[int] = typer.Option(None, "--column", "-c", help="Column number (0-indexed)"),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Symbol string (auto-calculates column)"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Programming language"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", "-r", help="Repository root path"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-readable output"),
    no_daemon: bool = typer.Option(False, "--no-daemon", help="Bypass daemon, boot fresh LSP"),
):
    """Get hover information (docs, types, signatures) at the given location."""
    try:
        lang_r, repo_r = _resolve_env(lang, repo_path, file_path)
        line_0 = line - 1
        line_0, col = resolve_column(repo_r, file_path, line_0, column, symbol)
        res = dispatch_lsp_request("hover", lang_r, repo_r, no_daemon, file_path=file_path, line=line_0, col=col)
        fmt = _get_format(human, False)
        print_output(res, fmt, title="Hover")
    except typer.Exit:
        raise
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# symbols (document symbols)
# ---------------------------------------------------------------------------

@app.command()
def symbols(
    file_path: str = typer.Option(..., "--file-path", "-f", help="Relative path to the file"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Programming language"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", "-r", help="Repository root path"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-readable output"),
    table: bool = typer.Option(False, "--table", "-T", help="Table output"),
    no_daemon: bool = typer.Option(False, "--no-daemon", help="Bypass daemon, boot fresh LSP"),
):
    """Get all symbols (classes, functions, variables) in a file."""
    try:
        lang_r, repo_r = _resolve_env(lang, repo_path, file_path)
        res = dispatch_lsp_request("document_symbols", lang_r, repo_r, no_daemon, file_path=file_path)
        fmt = _get_format(human, table)
        print_output(res, fmt, title="Document Symbols")
    except typer.Exit:
        raise
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# workspace-symbols
# ---------------------------------------------------------------------------

@app.command("workspace-symbols")
def workspace_symbols(
    query: str = typer.Option(..., "--query", "-q", help="Symbol name to search for"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Programming language"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", "-r", help="Repository root path"),
    context_lines: int = typer.Option(0, "--context", help="Surrounding lines to include"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-readable output"),
    table: bool = typer.Option(False, "--table", "-T", help="Table output"),
    no_daemon: bool = typer.Option(False, "--no-daemon", help="Bypass daemon, boot fresh LSP"),
):
    """Find symbols across the whole workspace matching a query."""
    try:
        lang_r, repo_r = _resolve_env(lang, repo_path)
        res = dispatch_lsp_request("workspace_symbol", lang_r, repo_r, no_daemon, query=query)
        res = add_context_to_locations(res or [], context_lines)
        fmt = _get_format(human, table)
        print_output(res, fmt, title="Workspace Symbols")
    except typer.Exit:
        raise
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# completions
# ---------------------------------------------------------------------------

@app.command()
def completions(
    file_path: str = typer.Option(..., "--file-path", "-f", help="Relative path to the file"),
    line: int = typer.Option(..., "--line", "-L", help="Line number (1-indexed)"),
    column: Optional[int] = typer.Option(None, "--column", "-c", help="Column number (0-indexed)"),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Symbol string (auto-calculates column)"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Programming language"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", "-r", help="Repository root path"),
    allow_incomplete: bool = typer.Option(True, "--allow-incomplete", help="Allow incomplete completion results"),
    human: bool = typer.Option(False, "--human", "-H", help="Human-readable output"),
    table: bool = typer.Option(False, "--table", "-T", help="Table output"),
    no_daemon: bool = typer.Option(False, "--no-daemon", help="Bypass daemon, boot fresh LSP"),
):
    """Get completions at the given location."""
    try:
        lang_r, repo_r = _resolve_env(lang, repo_path, file_path)
        line_0 = line - 1
        line_0, col = resolve_column(repo_r, file_path, line_0, column, symbol)
        res = dispatch_lsp_request(
            "completions", lang_r, repo_r, no_daemon,
            file_path=file_path, line=line_0, col=col, allow_incomplete=allow_incomplete,
        )
        fmt = _get_format(human, table)
        print_output(res, fmt, title="Completions")
    except typer.Exit:
        raise
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(code=1)
