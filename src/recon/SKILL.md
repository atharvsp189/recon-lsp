---
name: recon-skill
description: Structured recon workflow for codebase reconnaissance. Combines text search with LSP-powered semantic navigation.
---

# Recon Skills

Recon provides AST-based Language Server queries from the terminal. Combine it with `rg` for complete codebase reconnaissance.

## When to use what

- **`grep/rg`** — finding config values, env vars, log messages, string literals, comments, topic names. Fast, broad, no setup. Start here.
- **`recon`** — tracing a symbol to its definition across files, finding all callers of a function, understanding class hierarchies, navigating imports. Use when text search returns too many false positives or can't follow language-level indirection.

## Workflow — cheapest tool first

1. `rg` — broad text search across source, strings, comments, and config.
2. `recon workspace-symbols -q <Name>` — find classes, functions, and declarations across the workspace.
3. `recon symbols -f <path> --declarations-only` — structural outline of a single file.
4. `recon definition -f <path> -L <line> -s <name>` — jump to where a symbol is implemented.
5. `recon references -f <path> -L <line> -s <name>` — trace all callers and usages.
6. Read surrounding source before concluding behavior or guarantees.
7. `rg` again — catch string-only references that semantic indexing misses.

## Key flags and practices

- Use `-s <symbol>` instead of `--column` — auto-resolves within ±2 lines of `-L`.
- `--context N` embeds source snippets in JSON output. No need to read files separately.
- `recon batch -f queries.json` runs multiple lookups in one call — avoid looping.
- All line numbers are **1-indexed**.
- `--no-daemon` for one-off queries. `recon daemon start` for repeated queries in a session.
- Default output is JSON — do not use `--human` or `--table` as an agent.

## Default recommendation

Prefer `rg` for discovery and validation. Use recon when you need to follow symbol relationships that text search cannot resolve — definitions across modules, reference chains, or inherited methods.
