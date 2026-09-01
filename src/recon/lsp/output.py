"""
output.py — Output formatters for recon CLI.

Supports three modes:
  - JSON (default): Structured output for agents/pipelines
  - Human: Compact file:line format with optional code snippets
  - Table: Rich tables for terminal display
"""

import json
from typing import Any, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from recon.utils import ReconJSONEncoder

console = Console()


def print_json(data: Any) -> None:
    """Print structured JSON output (agent-friendly)."""
    print(json.dumps(data, cls=ReconJSONEncoder, indent=2))


def print_human(data: Any) -> None:
    """Print compact human-readable output."""
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and ("range" in item or "location" in item):
                loc = item.get("location", item)
                path = loc.get("relativePath") or loc.get("absolutePath", "unknown")
                line = loc.get("range", {}).get("start", {}).get("line", "?")
                name = item.get("name", "")
                label = f"  [dim]— {name}[/dim]" if name else ""
                console.print(f"  [cyan]{path}[/cyan]:[yellow]{line}[/yellow]{label}")

                context = item.get("context") or loc.get("context")
                if context:
                    console.print(Panel(
                        Syntax(context, "python", theme="monokai", line_numbers=False),
                        border_style="dim",
                        padding=(0, 1),
                    ))
            else:
                print(json.dumps(item, cls=ReconJSONEncoder))
    elif isinstance(data, dict):
        for key, val in data.items():
            console.print(f"  [bold]{key}[/bold]: {val}")
    elif isinstance(data, str):
        console.print(f"  {data}")
    else:
        print(json.dumps(data, cls=ReconJSONEncoder, indent=2))


def print_table(data: Any, title: str = "Results") -> None:
    """Print results as a Rich table."""
    if not isinstance(data, list) or not data:
        print_json(data)
        return

    # Infer columns from first item
    if isinstance(data[0], dict):
        table = Table(title=title, show_lines=True)
        cols = list(data[0].keys())
        # Skip large fields like 'context' in table view
        cols = [c for c in cols if c not in ("context", "context_error")]
        for col in cols:
            table.add_column(col, overflow="fold")
        for item in data:
            row = []
            for col in cols:
                val = item.get(col, "")
                if isinstance(val, dict):
                    val = json.dumps(val, cls=ReconJSONEncoder)
                row.append(str(val) if val is not None else "")
            table.add_row(*row)
        console.print(table)
    else:
        for item in data:
            console.print(f"  {item}")


def print_output(data: Any, fmt: str = "json", title: str = "Results") -> None:
    """Dispatch to the appropriate formatter."""
    if fmt == "human":
        print_human(data)
    elif fmt == "table":
        print_table(data, title)
    else:
        print_json(data)


def print_error(message: str) -> None:
    """Print a structured error (always JSON for agent consumption + Rich for terminal)."""
    console.print(f"[red bold]Error:[/red bold] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green bold]✓[/green bold] {message}")


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[blue bold]ℹ[/blue bold] {message}")
