"""
config.py — TOML-based configuration for recon.

Hierarchy (later overrides earlier):
  1. Global:  ~/.config/recon/config.toml
  2. Project: .recon.toml (in repo root)
  3. CLI flags (always win)
"""

import os
import json
import toml
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def get_global_config_dir() -> Path:
    """XDG-compliant global config directory."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    d = base / "recon"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_global_config_path() -> Path:
    return get_global_config_dir() / "config.toml"


def get_project_config_path(repo_path: Optional[str] = None) -> Path:
    root = Path(repo_path).resolve() if repo_path else Path.cwd()
    return root / ".recon.toml"


# ---------------------------------------------------------------------------
# TOML I/O
# ---------------------------------------------------------------------------

def _load_toml(path: Path) -> dict:
    if path.exists():
        try:
            return toml.load(path)
        except Exception:
            return {}
    return {}


def _save_toml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        toml.dump(data, f)


# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = [
    "python",
    "rust",
    "java",
    "typescript",
    "go",
    "ruby",
    "csharp",
    "cpp",
    "dart",
    "php",
    "elixir",
    "kotlin",
]

LANGUAGE_SERVERS = {
    "python": "jedi-language-server",
    "rust": "rust-analyzer",
    "java": "Eclipse JDT.LS",
    "typescript": "typescript-language-server",
    "go": "gopls",
    "ruby": "solargraph",
    "csharp": "OmniSharp",
    "cpp": "clangd",
    "dart": "dart language-server",
    "php": "intelephense",
    "elixir": "elixir-ls",
    "kotlin": "kotlin-language-server",
}


# ---------------------------------------------------------------------------
# Merged configuration
# ---------------------------------------------------------------------------

class ReconConfig:
    """
    Merged configuration from global + project files.
    CLI flags override everything at call sites (not stored here).
    """

    def __init__(
        self,
        language: Optional[str] = None,
        repo_path: Optional[str] = None,
        idle_timeout: int = 900,
        request_timeout: int = 30,
        default_format: str = "json",
        context_lines: int = 0,
    ):
        self.language = language
        self.repo_path = repo_path
        self.idle_timeout = idle_timeout
        self.request_timeout = request_timeout
        self.default_format = default_format
        self.context_lines = context_lines

    def to_dict(self) -> dict:
        return {
            "project": {
                "language": self.language or "",
                "repo_path": self.repo_path or "",
            },
            "daemon": {
                "idle_timeout": self.idle_timeout,
                "request_timeout": self.request_timeout,
            },
            "output": {
                "default_format": self.default_format,
                "context_lines": self.context_lines,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReconConfig":
        project = data.get("project", {})
        daemon = data.get("daemon", {})
        output = data.get("output", {})
        return cls(
            language=project.get("language") or None,
            repo_path=project.get("repo_path") or None,
            idle_timeout=daemon.get("idle_timeout", 900),
            request_timeout=daemon.get("request_timeout", 30),
            default_format=output.get("default_format", "json"),
            context_lines=output.get("context_lines", 0),
        )


def load_config(repo_path: Optional[str] = None) -> ReconConfig:
    """Load merged config: global defaults ← project overrides."""
    global_data = _load_toml(get_global_config_path())
    project_data = _load_toml(get_project_config_path(repo_path))

    # Deep merge: project overrides global
    merged: dict[str, Any] = {}
    for section in ("project", "daemon", "output"):
        merged[section] = {
            **global_data.get(section, {}),
            **project_data.get(section, {}),
        }

    return ReconConfig.from_dict(merged)


def save_project_config(config: ReconConfig, repo_path: Optional[str] = None) -> Path:
    """Save config to the project-level .recon.toml."""
    path = get_project_config_path(repo_path)
    _save_toml(path, config.to_dict())
    return path


def save_global_config(config: ReconConfig) -> Path:
    """Save config to the global config.toml."""
    path = get_global_config_path()
    _save_toml(path, config.to_dict())
    return path
