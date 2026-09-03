# Recon-LSP

**Context Engineering for your Codebase.**
Semantic code intelligence CLI for AI agents and developers.

<img src="../assets/recon-icon.png" width="100"/>

Recon turns Language Server Protocol (LSP) superpowers into simple terminal commands. No IDE required. It allows autonomous AI agents and developers to navigate large codebases efficiently. 

## The Problem with Text Search
When autonomous AI agents navigate large codebases, reading whole files doesn't make sense. The common fallback is `grep` or `ripgrep`, which provides text matching. However, this text-based search can be noisy, analyzing many fragments without proper context. This wastes tokens, increases tool calls, and may still miss the correct context.

## The LSP Solution
LSP (Language Server Protocol) builds a tree-like structure and provides true semantic understanding (what your IDE uses for IntelliSense). Recon leverages this to offer tools like:
- **Go to Definition**
- **Go to Reference**
- **Find Symbols**
- **Analyze Relationships**

This gets to the exact meaning and right context directly, without jumping over hundreds of tool calls. **Recon-LSP is not a replacement for text search, it complements it with smart semantic search.**

Recon-LSP provides **context engineering** for your codebase:
- **Less tokens used**
- **Fewer tool calls**
- **High quality context**

It sits as a separate tool from your IDE and can be used with **any** coding agent.

## Table of Contents
- [Installation](installation.md)
- [Usage Guide](usage.md)
- [Agent Integration](agent_integration.md)
