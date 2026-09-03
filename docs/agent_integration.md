# Agent Integration

Recon is primarily designed as a high-fidelity context engineering tool for autonomous AI agents. 

## The Problem: Token Bloat & Noise

When an AI agent (like a coding assistant) is given a task in a large codebase, it typically relies on standard text search (`grep` / `ripgrep`). While `grep` is powerful, it lacks an understanding of code structure:
- It returns every text match, including comments, strings, and unrelated uses.
- The agent has to read through noisy fragments, wasting its context window (tokens) and taking longer to reason.
- It often takes many iterative search commands (tool calls) to narrow down the actual definition or references.

## The Solution: Semantic Context Engineering

LSP (Language Server Protocol) is the engine that powers IDEs (like VS Code), providing Intellisense, auto-completion, and code navigation through Abstract Syntax Trees (ASTs).

By providing `recon` to an AI agent:
1. **Precision:** The agent can invoke `recon definition` or `recon references` to pinpoint exactly what it needs without hallucinating or guessing.
2. **Context Efficiency (Less Tokens):** Recon fetches only the specific context (surrounding lines, docstrings, exact signatures).
3. **Speed (Fewer Tool Calls):** Instead of looping `grep` and `cat`, the agent gets direct semantic answers in one command.

### How to use with AI Agents

Recon is **agent-agnostic**. Since it acts as a standalone CLI tool, any agent that can execute shell commands can use it. 

The output is formatted as JSON by default to ensure robust parsing by agents:

```bash
# Agent tool call
recon definition -f src/auth.py -L 20 -s authenticate
```

Output:
```json
{
  "file": "src/auth.py",
  "line": 45,
  "code_context": "def authenticate(user: User, token: str) -> bool:\n    ..."
}
```

By leveraging `recon-lsp`, coding agents operate with **eyes**—seeing the semantic relationships in the code rather than blindly matching substrings.
