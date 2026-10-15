"""
init_cmd.py — Interactive project setup wizard.

Guides the user through:
  1. Language selection
  2. Repository path confirmation
  3. Language server verification and auto-installation
  4. Config file creation
  5. Next steps
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from recon.commands.setup_cmd import (
    verify_server_probe,
)
from recon.config import (
    LANGUAGE_SERVERS,
    SUPPORTED_LANGUAGES,
    ReconConfig,
    get_project_config_path,
    load_config,
    save_project_config,
)
from recon.lsp.output import print_info, print_success

console = Console()

app = typer.Typer(help="Initialize a new recon project.")


def _display_languages() -> None:
    """Show a table of supported languages and their servers."""
    table = Table(title="Supported Languages", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Language", style="cyan bold")
    table.add_column("Language Server", style="green")

    for i, lang in enumerate(SUPPORTED_LANGUAGES, 1):
        server = LANGUAGE_SERVERS.get(lang, "unknown")
        table.add_row(str(i), lang, server)

    console.print(table)


@app.callback(invoke_without_command=True)
def init(
    repo_path: str | None = typer.Option(
        None,
        "--repo-path",
        "-r",
        help="Repository path (defaults to current directory)",
    ),
    language: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Skip interactive prompt and set language directly",
    ),
    skip_verify: bool = typer.Option(
        False,
        "--skip-verify",
        help="Skip language server verification",
    ),
):
    """
    Interactive setup wizard for recon.

    Sets up a .recon.toml config file and verifies/installs
    the language server.
    """
    console.print(
        Panel(
            "[bold blue]Recon — Code Reconnaissance Setup[/bold blue]\n\n"
            "This wizard will configure recon for your project.",
            border_style="blue",
        )
    )

    # 1. Resolve repo path
    if repo_path is None:
        default_path = str(Path.cwd())
        repo_path = Prompt.ask(
            "Repository path",
            default=default_path,
        )
    repo_path = str(Path(repo_path).resolve())
    console.print(f"  Repository: [cyan]{repo_path}[/cyan]")

    # Check if config already exists
    config_path = get_project_config_path(repo_path)
    if config_path.exists():
        existing = load_config(repo_path)
        console.print("\n  [yellow]Existing config found[/yellow]")
        if existing.language:
            console.print(f"    Language: [cyan]{existing.language}[/cyan]")
        if not Confirm.ask("  Overwrite existing configuration?", default=False):
            print_info("Setup cancelled. Existing config preserved.")
            raise typer.Exit()

    # 2. Select language
    if language is None:
        console.print()
        _display_languages()
        console.print()

        while True:
            choice = Prompt.ask(
                "Select a language (name or number)",
                default="python",
            )
            # Handle numeric input
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(SUPPORTED_LANGUAGES):
                    language = SUPPORTED_LANGUAGES[idx]
                    break
                else:
                    console.print("[red]Invalid number. Try again.[/red]")
            except ValueError:
                # Handle name input
                if choice.lower() in SUPPORTED_LANGUAGES:
                    language = choice.lower()
                    break
                else:
                    console.print(f"[red]Unknown language '{choice}'. Try again.[/red]")

    server = LANGUAGE_SERVERS.get(language, "unknown")
    console.print(f"\n  Language: [cyan bold]{language}[/cyan bold]")
    console.print(f"  Server:   [green]{server}[/green]")

    # 3. Verify language server & auto-install if missing
    if not skip_verify:
        console.print("\n  [dim]Checking language server...[/dim]")
        ok, msg = verify_server_probe(language, repo_path)
        if ok:
            print_success(f"Language server '{server}' is verified and ready!")
        else:
            console.print(
                f"\n [yellow]⚠Language server verification probe reported:[/yellow] {msg}"
            )

            # TODO: Automated installation is disabled for the MVP release.
            from recon.commands.setup_cmd import LANGUAGE_METADATA

            meta = LANGUAGE_METADATA.get(language, {})
            console.print(
                f"\n[bold]Automated installation is currently disabled. Please follow the manual instructions:[/bold]\n  {meta.get('manual_guide', '')}"
            )

            # if Confirm.ask(f"  Would you like to install '{server}' automatically now?", default=True):
            #     inst_ok, inst_msg = install_server(language, repo_path)
            #     if inst_ok:
            #         print_success("Installation succeeded! Re-verifying...")
            #         re_ok, re_msg = verify_server_probe(language, repo_path)
            #         if re_ok:
            #             print_success(f"Language server '{server}' is ready!")
            #         else:
            #             console.print(f"[yellow]Re-verification note:[/yellow] {re_msg}")
            #     else:
            #         print_error(f"Installation failed: {inst_msg}")
            #         if not Confirm.ask("  Continue configuration anyway?", default=True):
            #             raise typer.Exit(code=1)
            # else:
            if not Confirm.ask("\n  Continue configuration anyway?", default=True):
                raise typer.Exit(code=1)

    # 4. Save config
    config = ReconConfig(
        language=language,
        repo_path=repo_path,
    )
    saved_path = save_project_config(config, repo_path)
    print_success("Configuration saved")

    # 5. Show next steps
    console.print(
        Panel(
            "[bold green]Setup complete![/bold green]\n\n"
            "Try these commands:\n"
            "  [cyan]recon symbols -f <file>[/cyan]                     — List symbols in a file\n"
            "  [cyan]recon definition -f <file> -L <line> -s <sym>[/cyan]  — Jump to definition\n"
            "  [cyan]recon references -f <file> -L <line> -s <sym>[/cyan]  — Find all usages\n"
            "  [cyan]recon hover -f <file> -L <line> -s <sym>[/cyan]       — Docstrings & types\n"
            "  [cyan]recon daemon status[/cyan]                         — Check daemon status\n",
            title="Next Steps",
            border_style="green",
        )
    )
