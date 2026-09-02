"""
daemon_cmd.py — Daemon lifecycle management commands.

Commands:
  - start   — Start the background daemon
  - stop    — Gracefully shut down the daemon
  - status  — Show daemon status and cached LSP instances
  - restart — Stop + start
"""

import typer

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from recon.lsp.client import (
    is_daemon_alive,
    spawn_daemon,
    wait_for_daemon_socket,
    dispatch_request,
    get_daemon_dir,
    get_log_file,
)
from recon.lsp.output import print_success, print_error, print_info, print_json

console = Console()

app = typer.Typer(help="Manage the recon background daemon.")


@app.command()
def start():
    """Start the background daemon (auto-started on first LSP command too)."""
    if is_daemon_alive():
        print_info("Daemon is already running.")
        return
    spawn_daemon()
    if wait_for_daemon_socket():
        print_success("Daemon started successfully.")
    else:
        print_error("Daemon did not become ready in time. Check daemon log.")
        raise typer.Exit(code=1)


@app.command()
def stop():
    """Stop the background daemon gracefully."""
    if not is_daemon_alive():
        print_info("No daemon is currently running.")
        return
    try:
        result = dispatch_request({"cmd": "stop"})
        print_success(f"Daemon stopped: {result}")
    except Exception as e:
        print_error(f"Failed to stop daemon: {e}")
        raise typer.Exit(code=1)


@app.command()
def status():
    """Show daemon status and currently cached LSP instances."""
    if not is_daemon_alive():
        console.print(Panel(
            "[yellow bold]Daemon is not running.[/yellow bold]\n\n"
            "Start it with: [cyan]recon daemon start[/cyan]\n"
            "Or it will auto-start on first query.",
            title="Daemon Status",
            border_style="yellow",
        ))
        return

    try:
        result = dispatch_request({"cmd": "status"})
        cached = result.get("cached_lsps", [])

        if cached:
            table = Table(title="Cached LSP Instances", show_lines=False)
            table.add_column("Language", style="cyan bold")
            table.add_column("Repository", style="green")
            for entry in cached:
                table.add_row(entry["lang"], entry["repo_path"])

            console.print(Panel(
                "[green bold]Daemon is running.[/green bold]",
                title="Daemon Status",
                border_style="green",
            ))
            console.print(table)
        else:
            console.print(Panel(
                "[green bold]Daemon is running.[/green bold]\n\n"
                "[dim]No LSP instances cached yet. Run a query to warm up.[/dim]",
                title="Daemon Status",
                border_style="green",
            ))
        # Removed log output to keep it minimal
    except Exception:
        print_error("Daemon is running but unreachable.")


@app.command()
def restart():
    """Restart the daemon (stop + start)."""
    if is_daemon_alive():
        try:
            dispatch_request({"cmd": "stop"})
            print_info("Daemon stopped.")
        except Exception:
            pass

    # Wait a moment for cleanup
    import time
    time.sleep(0.5)

    spawn_daemon()
    if wait_for_daemon_socket():
        print_success("Daemon restarted successfully.")
    else:
        print_error("Daemon did not restart in time.")
        raise typer.Exit(code=1)
