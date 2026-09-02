"""
utils.py — Shared helpers for recon CLI.
"""

import json
import dataclasses
from pathlib import Path
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# JSON encoder that handles dataclasses
# ---------------------------------------------------------------------------

class ReconJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


# ---------------------------------------------------------------------------
# Column resolution from symbol name
# ---------------------------------------------------------------------------

def resolve_column(
    repo_path: str,
    file_path: str,
    line: int,
    column: Optional[int],
    symbol: Optional[str],
) -> tuple[int, int]:
    """
    Resolve a line and column number from either an explicit column or a symbol name.
    If --symbol is given, searches for the symbol on the given line (with ±2 line fuzzy search)
    and returns its (line, starting column).
    """
    if column is not None:
        return line, column
    if symbol is None:
        raise ValueError("You must provide either --column or --symbol.")

    full_path = Path(repo_path) / file_path
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        
        # Fuzzy search ±2 lines
        search_offsets = [0, 1, -1, 2, -2]
        for offset in search_offsets:
            test_line = line + offset
            if 0 <= test_line < len(lines):
                col = lines[test_line].find(symbol)
                if col != -1:
                    return test_line, col

        raise ValueError(f"Symbol '{symbol}' not found on or around line {line + 1} (1-indexed).")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Error reading file to resolve symbol: {e}")


# ---------------------------------------------------------------------------
# Context fetching — adds surrounding source lines to LSP locations
# ---------------------------------------------------------------------------

def add_context_to_locations(locations: List[dict], context_lines: int) -> List[dict]:
    """Enrich LSP location results with surrounding source code lines."""
    if context_lines <= 0:
        return locations
    for item in locations:
        loc = item.get("location", item)
        abs_path = loc.get("absolutePath")
        rng = loc.get("range")
        if abs_path and rng:
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                start_line = rng["start"]["line"]
                end_line = rng["end"]["line"]
                ctx_start = max(0, start_line - context_lines)
                ctx_end = min(len(lines), end_line + 1 + context_lines)
                item["context"] = "\n".join(lines[ctx_start:ctx_end])
            except Exception as e:
                item["context_error"] = str(e)
    return locations
