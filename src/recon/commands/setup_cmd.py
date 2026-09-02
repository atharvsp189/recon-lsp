"""
setup_cmd.py — Language server installation, diagnostics, and verification.

Provides automated & guided setup for language servers across all 12 supported
languages:
  - System prerequisite checks (Node, Go, Rust, Java, .NET, Ruby, Dart, etc.)
  - Automated installation (`recon setup <lang> --install`)
  - Diagnostic status overview (`recon setup`)
  - Fast probe verification (`recon setup <lang> --verify`)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import typer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from recon.config import SUPPORTED_LANGUAGES, LANGUAGE_SERVERS
from recon.lsp.output import print_success, print_error, print_info, print_json

console = Console()

app = typer.Typer(help="Install, diagnose, and verify language servers.")

# ---------------------------------------------------------------------------
# Metadata: Prerequisites & Installation configs
# ---------------------------------------------------------------------------

LANGUAGE_METADATA: Dict[str, Dict[str, Any]] = {
    "python": {
        "server": "jedi-language-server",
        "prereqs": ["python3", "pip"],
        "auto_download": False,
        "install_cmd": [sys.executable, "-m", "pip", "install", "jedi-language-server"],
        "manual_guide": "pip install jedi-language-server",
        "binary_names": ["jedi-language-server"],
    },
    "rust": {
        "server": "rust-analyzer",
        "prereqs": ["rustc", "cargo"],
        "auto_download": True,
        "install_cmd": ["rustup", "component", "add", "rust-analyzer"],
        "manual_guide": "Run: rustup component add rust-analyzer",
        "binary_names": ["rust-analyzer"],
    },
    "java": {
        "server": "Eclipse JDT.LS",
        "prereqs": ["java"],
        "min_version": "Java 17+",
        "auto_download": True,
        "install_cmd": None,
        "manual_guide": "macOS: brew install jdtls\n"
                        "Ubuntu/Debian: sudo apt install jdtls\n"
                        "Windows/Other: Download from https://projects.eclipse.org/projects/eclipse.jdt.ls",
        "binary_names": [],
    },
    "typescript": {
        "server": "typescript-language-server",
        "prereqs": ["node", "npm"],
        "auto_download": True,
        "install_cmd": ["npm", "install", "-g", "typescript-language-server", "typescript"],
        "manual_guide": "Run: npm install -g typescript-language-server typescript",
        "binary_names": ["typescript-language-server"],
    },
    "go": {
        "server": "gopls",
        "prereqs": ["go"],
        "auto_download": False,
        "install_cmd": ["go", "install", "golang.org/x/tools/gopls@latest"],
        "manual_guide": "Run: go install golang.org/x/tools/gopls@latest",
        "binary_names": ["gopls"],
    },
    "ruby": {
        "server": "solargraph",
        "prereqs": ["ruby", "gem"],
        "auto_download": False,
        "install_cmd": ["gem", "install", "solargraph"],
        "manual_guide": "Run: gem install solargraph",
        "binary_names": ["solargraph"],
    },
    "csharp": {
        "server": "OmniSharp",
        "prereqs": ["dotnet"],
        "min_version": ".NET SDK 6+",
        "auto_download": True,
        "install_cmd": None,
        "manual_guide": "Download OmniSharp from https://github.com/OmniSharp/omnisharp-roslyn/releases\n"
                        "Or use csharp-ls: dotnet tool install -g csharp-ls",
        "binary_names": ["OmniSharp"],
    },
    "cpp": {
        "server": "clangd",
        "prereqs": ["clangd"],
        "auto_download": False,
        "install_cmd": None,
        "manual_guide": "Ubuntu/Debian: sudo apt install clangd\n"
                        "macOS: brew install llvm\n"
                        "Windows: winget install LLVM.LLVM\n"
                        "Arch: sudo pacman -S clang\n"
                        "Fedora: sudo dnf install clang-tools-extra",
        "binary_names": ["clangd"],
    },
    "dart": {
        "server": "dart language-server",
        "prereqs": ["dart"],
        "auto_download": False,
        "install_cmd": ["dart", "pub", "global", "activate", "dart_language_server"],
        "manual_guide": "Run: dart pub global activate dart_language_server",
        "binary_names": ["dart_language_server"],
    },
    "php": {
        "server": "intelephense",
        "prereqs": ["npm"],
        "auto_download": True,
        "install_cmd": ["npm", "install", "-g", "intelephense"],
        "manual_guide": "Run: npm install -g intelephense",
        "binary_names": ["intelephense"],
    },
    "elixir": {
        "server": "elixir-ls",
        "prereqs": ["elixir", "erl"],
        "min_version": "Elixir 1.13+, Erlang 24+",
        "auto_download": True,
        "install_cmd": None,
        "manual_guide": "Download release from https://github.com/elixir-lsp/elixir-ls/releases\n"
                        "Or build from source: mix compile && mix elixir_ls.release",
        "binary_names": [],
    },
    "kotlin": {
        "server": "kotlin-language-server",
        "prereqs": ["java"],
        "min_version": "Java 11+",
        "auto_download": True,
        "install_cmd": None,
        "manual_guide": "macOS: brew install kotlin-language-server\n"
                        "Other: Download release from https://github.com/fwcd/kotlin-language-server/releases",
        "binary_names": [],
    },
}


# ---------------------------------------------------------------------------
# Diagnostics & Check Helpers
# ---------------------------------------------------------------------------

def check_prerequisites(language: str) -> Tuple[bool, List[str], List[str]]:
    """
    Check if required system tools (e.g. node, go, cargo, java) are installed.
    Returns (all_present, found_list, missing_list).
    """
    meta = LANGUAGE_METADATA.get(language, {})
    prereqs = meta.get("prereqs", [])
    found = []
    missing = []

    for tool in prereqs:
        if shutil.which(tool) is not None:
            found.append(tool)
        else:
            # Special check for python
            if tool == "pip" and shutil.which("pip3") is not None:
                found.append("pip3")
            elif tool == "python3" and shutil.which("python") is not None:
                found.append("python")
            else:
                missing.append(tool)

    return len(missing) == 0, found, missing


def check_server_binary(language: str) -> Tuple[bool, Optional[str]]:
    """
    Check if the LSP server binary is directly executable in PATH or cached by multilspy.
    """
    meta = LANGUAGE_METADATA.get(language, {})
    bin_names = meta.get("binary_names", [])

    for b in bin_names:
        found_path = shutil.which(b)
        if found_path:
            return True, found_path

    # Check multilspy cache directory (~/.multilspy/lsp/)
    lsp_cache_dir = Path.home() / ".multilspy" / "lsp"
    if lsp_cache_dir.exists():
        # Check for matching directory or executable
        for p in lsp_cache_dir.glob(f"**/*{language}*"):
            if p.is_file() and os.access(p, os.X_OK):
                return True, str(p)

    # For Python: check if importable
    if language == "python":
        try:
            import jedi_language_server  # noqa
            return True, "python module (jedi_language_server)"
        except ImportError:
            pass

    return False, None


def verify_server_probe(language: str, repo_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Boot the language server via multilspy for a fast probe test.
    """
    test_dir = repo_path or tempfile.gettempdir()
    try:
        from multilspy import SyncLanguageServer
        from multilspy.multilspy_config import MultilspyConfig
        from multilspy.multilspy_logger import MultilspyLogger

        config = MultilspyConfig.from_dict({"code_language": language})
        logger = MultilspyLogger()
        lsp = SyncLanguageServer.create(config, logger, str(Path(test_dir).resolve()), timeout=15)
        with lsp.start_server():
            return True, "Server started and responded to initialize handshake successfully."
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Installation Logic
# ---------------------------------------------------------------------------

def install_server(language: str, repo_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Execute automated installation or trigger multilspy's runtime dependency fetch.
    """
    meta = LANGUAGE_METADATA.get(language, {})
    has_prereqs, found, missing = check_prerequisites(language)

    if not has_prereqs:
        return False, f"Missing system prerequisite tools: {', '.join(missing)}. Please install them first."

    install_cmd = meta.get("install_cmd")
    auto_download = meta.get("auto_download", False)

    # TODO: Automated installation disabled for MVP. 
    # Enable this in a future release once cross-platform permissions and multilspy downloads are bulletproof.
    # if install_cmd:
    #     console.print(f"  [dim]Running installation:[/dim] [cyan]{' '.join(install_cmd)}[/cyan]")
    #     try:
    #         res = subprocess.run(
    #             install_cmd,
    #             capture_output=True,
    #             text=True,
    #             check=False,
    #         )
    #         if res.returncode == 0:
    #             return True, "Installation command finished successfully."
    #         else:
    #             err = res.stderr.strip() or res.stdout.strip()
    #             return False, f"Installation failed with code {res.returncode}:\n{err}"
    #     except Exception as e:
    #         return False, f"Error running installation command: {e}"
    #
    # if auto_download:
    #     console.print(f"  [dim]Triggering automatic download & setup via multilspy...[/dim]")
    #     ok, msg = verify_server_probe(language, repo_path)
    #     if ok:
    #         return True, "Language server downloaded and verified successfully."
    #     else:
    #         return False, f"Automatic download/initialization failed: {msg}"

    return False, f"Automated installation is currently disabled. Please follow the manual instructions:\n\n{meta.get('manual_guide', '')}"


# ---------------------------------------------------------------------------
# CLI Command
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def setup(
    language: Optional[str] = typer.Argument(
        None,
        help="Language to diagnose, install, or verify (e.g., python, rust, typescript, go)",
    ),
    install: bool = typer.Option(
        False, "--install", "-i",
        help="Automatically install/download the language server",
    ),
    verify_only: bool = typer.Option(
        False, "--verify", "-v",
        help="Run verification probe only (clean exit code)",
    ),
    repo_path: Optional[str] = typer.Option(
        None, "--repo-path", "-r",
        help="Repository path for verification test",
    ),
    as_json: bool = typer.Option(
        False, "--json", "-j",
        help="Output diagnostics as structured JSON",
    ),
):
    """
    🔧 Install, diagnose, and verify language servers.

    Without arguments: displays diagnostic status overview of all 12 supported languages.
    With language argument: diagnoses prerequisites, verifies probe, or installs with --install.
    """
    if language is None:
        _show_all_languages_diagnostics(as_json)
        return

    language = language.lower()
    if language not in SUPPORTED_LANGUAGES:
        print_error(f"Unknown language '{language}'. Supported: {', '.join(SUPPORTED_LANGUAGES)}")
        raise typer.Exit(code=1)

    meta = LANGUAGE_METADATA.get(language, {})
    server_name = meta.get("server", "unknown")

    # Diagnostic data collector
    has_prereqs, found_prereqs, missing_prereqs = check_prerequisites(language)
    has_bin, bin_location = check_server_binary(language)

    # 1. JSON output mode (agent-friendly)
    if as_json:
        probe_ok, probe_msg = False, "Not verified"
        if verify_only or has_bin:
            probe_ok, probe_msg = verify_server_probe(language, repo_path)
        diag = {
            "language": language,
            "server": server_name,
            "prerequisites_met": has_prereqs,
            "prerequisites_found": found_prereqs,
            "prerequisites_missing": missing_prereqs,
            "binary_detected": has_bin,
            "binary_path": bin_location,
            "auto_download_supported": meta.get("auto_download", False),
            "probe_verified": probe_ok,
            "probe_message": probe_msg,
            "install_guide": meta.get("manual_guide"),
        }
        print_json(diag)
        if verify_only and not probe_ok:
            raise typer.Exit(code=1)
        return

    # 2. Verify-only mode
    if verify_only:
        console.print(f"[dim]Verifying {server_name} for '{language}'...[/dim]")
        ok, msg = verify_server_probe(language, repo_path)
        if ok:
            print_success(f"{server_name} for {language} is installed and working!")
        else:
            print_error(f"Verification failed: {msg}")
            raise typer.Exit(code=1)
        return

    # 3. Interactive / Full diagnosis & install mode
    console.print(Panel(
        f"[bold cyan]Language:[/bold cyan]       {language}\n"
        f"[bold cyan]Language Server:[/bold cyan] [green]{server_name}[/green]\n"
        f"[bold cyan]Prerequisites:[/bold cyan]   {', '.join(found_prereqs) if found_prereqs else 'none'} "
        f"{'([red]missing: ' + ', '.join(missing_prereqs) + '[/red])' if missing_prereqs else '[green]✓ all met[/green]'}\n"
        f"[bold cyan]Binary Status:[/bold cyan]   {'[green]✓ Found[/green]' if has_bin else '[yellow]Not detected in PATH[/yellow]'}\n"
        f"[bold cyan]Auto-Download:[/bold cyan]   {'[green]Yes (via multilspy)[/green]' if meta.get('auto_download') else 'No (requires package manager)'}",
        title=f"🔍 Language Server Diagnostics: {language.upper()}",
        border_style="cyan",
    ))

    # Install requested or missing binary
    if install:
        console.print(f"\n[bold blue]Starting installation for {server_name}...[/bold blue]")
        ok, msg = install_server(language, repo_path)
        if ok:
            print_success(f"Installation completed: {msg}")
        else:
            print_error(f"Installation failed: {msg}")
            raise typer.Exit(code=1)

    # Perform probe verification
    console.print(f"\n[dim]Probing {server_name} startup...[/dim]")
    probe_ok, probe_msg = verify_server_probe(language, repo_path)
    if probe_ok:
        print_success(f"Language server '{server_name}' is fully operational! ✨")
    else:
        console.print(f"[yellow]⚠ Server probe failed:[/yellow] {probe_msg}")
        
        # TODO: Automated installation is disabled for the MVP release.
        # if not install and (meta.get("install_cmd") or meta.get("auto_download")):
        #     if Confirm.ask("\nWould you like to run automated installation now?", default=True):
        #         ok, msg = install_server(language, repo_path)
        #         if ok:
        #             print_success(f"Installation completed! Re-verifying...")
        #             probe_ok, probe_msg = verify_server_probe(language, repo_path)
        #             if probe_ok:
        #                 print_success(f"Language server '{server_name}' is now working! ✨")
        #                 return
        #             else:
        #                 print_error(f"Re-verification failed: {probe_msg}")
        #         else:
        #             print_error(f"Installation failed: {msg}")
        # else:
        console.print(f"\n[bold]Manual installation instructions:[/bold]\n  {meta.get('manual_guide')}")


def _show_all_languages_diagnostics(as_json: bool = False) -> None:
    """Display real-time diagnostic table for all 12 supported languages."""
    records = []
    for lang in SUPPORTED_LANGUAGES:
        meta = LANGUAGE_METADATA.get(lang, {})
        has_prereqs, found, missing = check_prerequisites(lang)
        has_bin, bin_loc = check_server_binary(lang)
        auto_dl = meta.get("auto_download", False)

        if has_bin:
            status = "[green]✓ Installed[/green]"
            action = "Ready to use"
        elif auto_dl and has_prereqs:
            status = "[cyan]⚡ Auto-downloads[/cyan]"
            action = f"Manual install"
        elif not has_prereqs:
            status = "[red]✗ Toolchain missing[/red]"
            action = f"Install {', '.join(missing)}"
        else:
            status = "[yellow]⚠ Server missing[/yellow]"
            action = f"Manual install"

        records.append({
            "language": lang,
            "server": meta.get("server", "unknown"),
            "status_label": status,
            "prerequisites_met": has_prereqs,
            "missing_prereqs": missing,
            "binary_detected": has_bin,
            "action": action,
            "install_guide": meta.get("manual_guide", "").split("\n")[0],
        })

    if as_json:
        print_json(records)
        return

    table = Table(title="🔍 Recon Language Server Diagnostics", show_lines=False)
    table.add_column("Language", style="cyan bold", width=12)
    table.add_column("Language Server", style="green", width=26)
    table.add_column("Status", width=22)
    table.add_column("Action / Install Command", style="dim")

    for r in records:
        table.add_row(r["language"], r["server"], r["status_label"], r["action"])

    console.print(table)
    console.print(
        "\n  [dim]View manual install instructions:[/dim] [cyan]recon setup <language>[/cyan]\n"
        "  [dim]Test verification probe with:[/dim]     [cyan]recon setup <language> --verify[/cyan]"
    )
