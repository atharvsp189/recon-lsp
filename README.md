# 🔍 Recon — LSP-Powered Code Reconnaissance

[![PyPI version](https://badge.fury.io/py/recon-lsp.svg)](https://badge.fury.io/py/recon-lsp)
[![Python Versions](https://img.shields.io/pypi/pyversions/recon-lsp.svg)](https://pypi.org/project/recon-lsp/)

Context Engineering for your Codebase. Semantic code intelligence CLI for AI agents.   

Recon turns Language Server Protocol superpowers into simple terminal commands. No IDE required.

---

## 📦 Installation

### Option 1: Install globally via `uv` or `pipx` (Recommended)
This makes `recon` accessible from anywhere in your terminal:
```bash
uv tool install recon-lsp
# or
pipx install recon-lsp
```

### Option 2: Install into active Python environment / venv
```bash
pip install recon-lsp
# or with uv:
uv pip install recon-lsp
```

### Option 3: Run without installing via `uv run`
```bash
uvx recon-lsp --help
```

---

## 🚀 Quick Start

```bash
# 1. Interactive setup (creates .recon.toml in current repo)
recon init

# Or manually configure your workspace:
recon config --lang python --repo-path /path/to/your/repo

# 2. Check language server diagnostics & auto-install if needed:
recon setup                        # Diagnostic status overview of all 12 languages
recon setup python                 # Diagnose & verify Python LSP
recon setup php --install          # Automatically install / download LSP

# 3. Start querying your codebase:
recon symbols -f src/main.py --human
recon definition -f src/main.py -L 10 -s MyClass --context 3 --human
recon references -f src/main.py -L 10 -s MyClass --human
recon hover -f src/main.py -L 10 -s MyClass
```

---

## 🛠️ Commands Reference

### Setup & Configuration

| Command | Description |
|---|---|
| `recon init` | Interactive setup wizard (TUI with language picker & auto-verification) |
| `recon setup` | Real-time diagnostic table for all 12 supported languages |
| `recon setup <lang>` | Diagnose prerequisites & verify language server probe |
| `recon setup <lang> -i` | Automatically install / download the language server |
| `recon setup <lang> -v` | Fast probe verification only (clean exit code for scripts/CI) |
| `recon setup <lang> -j` | Output diagnostics as structured JSON for AI agents |
| `recon config --lang <l>` | Set project defaults (`.recon.toml`) |
| `recon info` | Show current config, daemon status, and paths |

### 🔍 LSP Queries

| Command | Description |
|---|---|
| `recon definition -f <file> -L <line> -s <sym>` | Jump to symbol definition |
| `recon references -f <file> -L <line> -s <sym>` | Find all references across codebase |
| `recon hover -f <file> -L <line> -s <sym>` | Extract docstrings, type signatures, hover details |
| `recon symbols -f <file>` | List all classes, functions, variables in a file |
| `recon workspace-symbols -q <query>` | Search symbols across the entire workspace |
| `recon completions -f <file> -L <line> -s <sym>` | Get context-aware autocompletions |

### 🔧 Daemon Management

The daemon **auto-starts** on your first query. You can also control it manually:

| Command | Description |
|---|---|
| `recon daemon start` | Pre-warm the background daemon |
| `recon daemon stop` | Gracefully shut down daemon and LSP child processes |
| `recon daemon status` | Show running status and cached LSP server instances |
| `recon daemon restart` | Stop and restart the daemon |

---

## 🖥️ Output Formats

```bash
# JSON (default, ideal for AI agents and automated scripts)
recon symbols -f main.py

# Human-readable (compact file:line format with syntax-highlighted snippets)
recon symbols -f main.py --human

# Rich table (styled terminal table view)
recon symbols -f main.py --table
```

---

## ⚙️ Core Flags

| Flag | Short | Description |
|---|---|---|
| `--file-path` | `-f` | Relative path to the file |
| `--line` | `-L` | Line number (0-indexed) |
| `--symbol` | `-s` | Symbol name (auto-calculates column, eliminating manual indexing) |
| `--column` | `-c` | Column number (alternative to `--symbol`) |
| `--lang` | `-l` | Language (overrides saved config) |
| `--repo-path` | `-r` | Repository root (overrides saved config) |
| `--context <N>` | | Number of surrounding lines to fetch for matched locations |
| `--human` | `-H` | Human-readable formatted output |
| `--table` | `-T` | Rich table terminal output |
| `--no-daemon` | | Bypass daemon and run in-process (for debugging or isolated CI) |

---

## 🌐 Supported Languages & Tools

| Language | Language Server | Setup Support |
|---|---|---|
| **Python** | jedi-language-server | `pip install jedi-language-server` |
| **Rust** | rust-analyzer | Auto-download / `rustup component add rust-analyzer` |
| **Java** | Eclipse JDT.LS | Auto-download (Requires Java 17+) |
| **TypeScript / JS** | typescript-language-server | Auto-install via npm / multilspy |
| **Go** | gopls | `go install golang.org/x/tools/gopls@latest` |
| **Ruby** | solargraph | `gem install solargraph` |
| **C#** | OmniSharp | Auto-download (Requires .NET 6+) |
| **C / C++** | clangd | System package manager (`apt install clangd`, `brew install llvm`) |
| **Dart** | dart language-server | Built into Dart SDK / `dart pub global activate` |
| **PHP** | intelephense | Auto-install via npm |
| **Elixir** | elixir-ls | Auto-download (Requires Elixir 1.13+, Erlang 24+) |
| **Kotlin** | kotlin-language-server | Auto-download (Requires Java 11+) |

Run `recon setup` to see real-time toolchain and installation diagnostics for all languages on your system.
