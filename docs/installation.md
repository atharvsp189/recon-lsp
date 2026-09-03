# Installation

`recon-lsp` is officially published on PyPI.

## Option 1: Global Installation (Recommended)

Installing globally makes `recon` accessible from anywhere in your terminal. We recommend using `uv` or `pipx`:

```bash
uv tool install recon-lsp
# or
pipx install recon-lsp
```

## Option 2: Local / Virtual Environment Installation

If you prefer to install it into an active Python environment or a specific virtual environment:

```bash
pip install recon-lsp
# or with uv:
uv pip install recon-lsp
```

## Option 3: Run without installing

You can also run Recon on-the-fly using `uv run`:

```bash
uvx recon-lsp --help
```

## Setup

Once installed, you can configure it for your project:

```bash
# Interactive setup (creates .recon.toml in current repo)
recon init

# Or manually configure your workspace:
recon config --lang python --repo-path /path/to/your/repo
```
