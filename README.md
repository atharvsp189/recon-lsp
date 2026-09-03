# Recon — LSP-Powered Code Reconnaissance

[![PyPI version](https://badge.fury.io/py/recon-lsp.svg)](https://badge.fury.io/py/recon-lsp)
[![Python Versions](https://img.shields.io/pypi/pyversions/recon-lsp.svg)](https://pypi.org/project/recon-lsp/)

Context Engineering for your Codebase. Semantic code intelligence CLI for AI agents.   

Recon turns Language Server Protocol superpowers into simple terminal commands. No IDE required.

---

## Installation

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

## Quick Start

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

## Commands Reference

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
| `recon agent-skill` | Print the recon-skills reconnaissance workflow for AI agents |

### LSP Queries

| Command | Description |
|---|---|
| `recon definition -f <file> -L <line> -s <sym>` | Jump to symbol definition |
| `recon references -f <file> -L <line> -s <sym>` | Find all references across codebase |
| `recon hover -f <file> -L <line> -s <sym>` | Extract docstrings, type signatures, hover details |
| `recon symbols -f <file>` | List all classes, functions, variables in a file |
| `recon workspace-symbols -q <query>` | Search symbols across the entire workspace |
| `recon completions -f <file> -L <line> -s <sym>` | Get context-aware autocompletions |
| `recon batch -f <queries.json>` | Run multiple LSP queries from a JSON file in one go |

### Daemon Management

The daemon **auto-starts** on your first query. You can also control it manually:

| Command | Description |
|---|---|
| `recon daemon start` | Pre-warm the background daemon |
| `recon daemon stop` | Gracefully shut down daemon and LSP child processes |
| `recon daemon status` | Show running status and cached LSP server instances |
| `recon daemon restart` | Stop and restart the daemon |

---

## Output Formats

```bash
# JSON (default, ideal for AI agents and automated scripts)
recon symbols -f main.py

# Human-readable (compact file:line format with syntax-highlighted snippets)
recon symbols -f main.py --human

# Rich table (styled terminal table view)
recon symbols -f main.py --table
```

---

## Core Flags

| Flag | Short | Description |
|---|---|---|
| `--file-path` | `-f` | Relative path to the file |
| `--line` | `-L` | Line number **(1-indexed)** |
| `--symbol` | `-s` | Symbol name. Used instead of column. (Fuzzy searches ±2 lines if not exactly on `-L`) |
| `--column` | `-c` | Column number (0-indexed). Alternative to `--symbol` |
| `--lang` | `-l` | Language (Optional. Auto-detected from file extension) |
| `--repo-path` | `-r` | Repository root (Defaults to current directory) |
| `--context <N>` | | Number of surrounding lines to fetch for matched locations |
| `--human` | `-H` | Human-readable formatted output |
| `--table` | `-T` | Rich table terminal output |
| `--no-daemon` | | Bypass daemon and run in-process |

---

## For AI Agents

`recon` is heavily optimized for use by LLMs and AI Agents. When using `recon` as an agent, keep these tips in mind:

1. **Use `--symbol` instead of `--column`**: Never guess column numbers! Just pass the line number (`-L`) and the exact string symbol (`-s`). `recon` will automatically resolve the column.
2. **Fuzzy Line Matching**: If your line number is slightly off due to recent edits, `recon` will automatically search ±2 lines around your `-L` parameter to find the symbol.
3. **Automatic Language Detection**: You can omit `-l` (e.g., `-l python`); `recon` infers it directly from the `--file-path` extension.
4. **Always use `--context`**: Pass `--context 3` or `--context 5` when running `definition` or `references`. This embeds the actual source code directly in the JSON response, saving you from running `cat` or `view_file` later!
5. **Default Output is JSON**: Do not pass `--human` or `--table` if you are an agent. The default JSON output is structured and parses perfectly into your context window.
6. **Batch Queries**: Use `recon batch -f queries.json` to execute multiple queries at once. This avoids starting up the process multiple times and can run instantly via the daemon. 

Example Agent Command (Single):
```bash
recon definition -f src/recon/utils.py -L 26 -s resolve_column --context 5
```

Example Agent Command (Batch):
```json
[
  {
    "command": "definition",
    "file_path": "src/recon/utils.py",
    "line": 26,
    "symbol": "resolve_column",
    "context_lines": 3
  },
  {
    "command": "workspace-symbols",
    "query": "dispatch_lsp_request",
    "lang": "python"
  }
]
```
```bash
recon batch -f queries.json
```

---

## Supported Languages & Tools

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

---

## Language Specific Notes & Troubleshooting

Since `recon` leverages real Language Servers, it expects your project to be in a buildable/analyzable state. Here are the requirements for accurate results across all supported languages:

* **Python**: Ensure third-party dependencies are installed in your active environment (`venv`, `poetry`, `uv`) so the language server can resolve external imports.
* **TypeScript / JavaScript**: You must run `npm install`, `yarn`, or `pnpm install`. The compiler cannot build an accurate AST without `node_modules` present.
* **C / C++**: You must generate a `compile_commands.json` at the root of your project (e.g., using `cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=1`). Without this, `clangd` degrades into a basic, less-accurate parser.
* **Go**: Ensure the `go` binary is installed in your `PATH`. Running `go mod tidy` or `go mod download` is highly recommended before querying to resolve all external packages.
* **Rust**: Ensure your code successfully checks (`cargo check`). The `rust-analyzer` needs a valid `Cargo.toml` to index macros and dependencies properly.
* **Java**: The project must be properly configured with `pom.xml` (Maven) or `build.gradle` (Gradle). Note: The Eclipse JDT.LS backend requires Java 17+ installed on your system.
* **C#**: Requires the .NET 6+ SDK. Ensure you have restored your `.sln` or `.csproj` files (e.g., `dotnet restore`) so NuGet packages are resolved.
* **Ruby**: Run `bundle install` and `yard gems` to ensure documentation and gem dependencies are available to the `solargraph` server.
* **PHP**: Run `composer install` to download dependencies for accurate symbol resolution via `intelephense`.
* **Elixir**: Requires Elixir 1.13+ and Erlang 24+. Run `mix deps.get` to fetch dependencies for `elixir-ls`.
* **Kotlin**: Requires Java 11+. Ensure your Gradle/Maven wrappers are functional and dependencies are synced.
* **Dart**: Run `dart pub get` or `flutter pub get` to resolve packages for the built-in Dart analysis server.
