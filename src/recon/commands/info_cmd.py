"""
info_cmd.py — Display project info, config, and supported languages.
"""


import typer
from rich.console import Console
from rich.panel import Panel

from recon import __version__
from recon.config import (
    get_global_config_path,
    get_project_config_path,
    load_config,
)
from recon.lsp.client import is_daemon_alive

console = Console()

app = typer.Typer(help="Show project info and status.")


@app.callback(invoke_without_command=True)
def info(
    repo_path: str | None = typer.Option(
        None,
        "--repo-path",
        "-r",
        help="Repository path",
    ),
):
    """Show recon project configuration, daemon status, and supported languages."""
    cfg = load_config(repo_path)

    # Project info
    project_config = get_project_config_path(repo_path)
    global_config = get_global_config_path()

    project_status = "✓ found" if project_config.exists() else "✗ not found"
    global_status = "✓ found" if global_config.exists() else "✗ not found"
    daemon_running = (
        "[green]running[/green]" if is_daemon_alive() else "[yellow]stopped[/yellow]"
    )

    info_text = (
        f"[bold]Version:[/bold]        {__version__}\n"
        f"[bold]Language:[/bold]       {cfg.language or '[dim]not set[/dim]'}\n"
        f"[bold]Daemon:[/bold]         {daemon_running}\n"
        f"\n"
        f"[bold]Config Status:[/bold]\n"
        f"  Project: {project_status}\n"
        f"  Global:  {global_status}\n"
        f"\n"
        f"[bold]Settings:[/bold]\n"
        f"  Output Format: {cfg.default_format}\n"
        f"  Context Lines: {cfg.context_lines}\n"
        f"  Idle Timeout:  {cfg.idle_timeout}s\n"
        f"  Request Timeout: {cfg.request_timeout}s"
    )

    console.print(
        Panel(
            info_text,
            title="Recon Info",
            border_style="blue",
        )
    )
