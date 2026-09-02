"""
main.py — Recon CLI entry point.

Registers all command groups and sub-commands under a single Typer app.

Usage:
    recon init                          # Interactive setup wizard
    recon setup [language]              # Diagnose, install, or verify language servers
    recon definition -f main.py ...     # LSP query commands
    recon daemon start|stop|status      # Daemon lifecycle
    recon info                          # Show project config & status
    recon config --lang python          # Set/view config
"""

import json
import typer
from pathlib import Path
from typing import Optional

from rich.console import Console

from recon.config import (
    load_config,
    save_project_config,
    save_global_config,
    ReconConfig,
    get_project_config_path,
)
from recon.lsp.output import print_success, print_json

# Import commands
from recon.commands.init_cmd import init
from recon.commands.setup_cmd import setup
from recon.commands.daemon_cmd import app as daemon_app
from recon.commands.info_cmd import info
from recon.commands.query import (
    definition, references, hover, symbols, workspace_symbols, completions, batch,
)

console = Console()

# ---------------------------------------------------------------------------
# Root app
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="recon",
    help="🔍 Recon — LSP-powered code reconnaissance for AI agents and humans.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# ---------------------------------------------------------------------------
# Register core commands
# ---------------------------------------------------------------------------

# `recon init` — interactive setup wizard
app.command("init", help="🔍 Initialize a new recon project with interactive wizard.")(init)

# `recon setup` — language server diagnostics, installer, and verification
app.command("setup", help="🔧 Diagnose, install, or verify language servers.")(setup)

# `recon info` — project info display
app.command("info", help="ℹ️  Show project info, daemon status, and config paths.")(info)

# `recon daemon start|stop|status|restart` — daemon lifecycle subgroup
app.add_typer(daemon_app, name="daemon")


# ---------------------------------------------------------------------------
# LSP query commands — registered directly on root app for flat access
# ---------------------------------------------------------------------------

app.command("definition", help="Find the definition of a symbol at the given location.")(definition)
app.command("references", help="Find all references to a symbol at the given location.")(references)
app.command("hover", help="Get hover information (docs, types, signatures) at the given location.")(hover)
app.command("symbols", help="Get all symbols (classes, functions, variables) in a file.")(symbols)
app.command("workspace-symbols", help="Find symbols across the whole workspace matching a query.")(workspace_symbols)
app.command("completions", help="Get completions at the given location.")(completions)
app.command("batch", help="Run multiple LSP queries from a JSON file in one go.")(batch)


# ---------------------------------------------------------------------------
# Config command (simple, on root)
# ---------------------------------------------------------------------------

@app.command("config", help="⚙️  View or set configuration defaults.")
def config(
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Default language"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", "-r", help="Default repo path"),
    show: bool = typer.Option(False, "--show", help="Show current config"),
    set_global: bool = typer.Option(False, "--global", "-g", help="Set global defaults instead of project"),
):
    """View or set configuration defaults."""
    if show:
        cfg = load_config(repo_path)
        print_json(cfg.to_dict())
        return

    if not lang and not repo_path:
        # Show current config if no flags
        cfg = load_config(repo_path)
        print_json(cfg.to_dict())
        return

    cfg = load_config(repo_path)
    if lang:
        cfg.language = lang
    if repo_path:
        cfg.repo_path = str(Path(repo_path).resolve())

    if set_global:
        path = save_global_config(cfg)
    else:
        path = save_project_config(cfg, repo_path)

    print_success(f"Config saved")
    print_json(cfg.to_dict())


if __name__ == "__main__":
    app()
