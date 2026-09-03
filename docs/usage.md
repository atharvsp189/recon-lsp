# Usage Guide

Recon provides a rich set of commands to interact with your codebase using the Language Server Protocol.

## 🚀 Quick Start

```bash
# 1. Start querying your codebase immediately:
recon symbols -f src/main.py --human

recon definition -f src/main.py -L 10 -s MyClass --context 3 --human

recon references -f src/main.py -L 10 -s MyClass --human

recon hover -f src/main.py -L 10 -s MyClass
```

## 🛠️ Commands Reference

### Setup & Configuration

| Command | Description |
|---|---|
| `recon init` | Interactive setup wizard (TUI with language picker & auto-verification) |
| `recon setup` | Real-time diagnostic table for all 12 supported languages |
| `recon setup <lang>` | Diagnose prerequisites & verify language server probe |
| `recon setup <lang> -i` | Automatically install / download the language server |
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

The daemon **auto-starts** on your first query, but you can manage it manually:

| Command | Description |
|---|---|
| `recon daemon start` | Pre-warm the background daemon |
| `recon daemon stop` | Gracefully shut down daemon and LSP child processes |
| `recon daemon status` | Show running status and cached LSP server instances |

## 🖥️ Output Formats

By default, Recon outputs JSON, which is ideal for AI agents and automated scripts. However, you can format the output for human readability:

```bash
# JSON (default)
recon symbols -f main.py

# Human-readable (compact file:line format with syntax-highlighted snippets)
recon symbols -f main.py --human

# Rich table (terminal table view)
recon symbols -f main.py --table
```
