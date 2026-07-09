"""Shared helpers for the walk-forward validation research scripts
(``walk_forward_validation.py`` and ``greenblatt_walk_forward.py`` at the
repo root). Not part of the pytest suite - these are one-off analysis tools,
kept here only to avoid the two scripts drifting on formatting logic.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path


def setup_backend_path() -> None:
    """Make AlphaLab's ``backend/`` importable regardless of cwd."""
    backend = str(Path(__file__).resolve().parent.parent / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)


def fmt(value, fmt_str: str, na: str = "  N/A  ") -> str:
    """Format a numeric value, returning `na` if it's None/NaN/unformattable."""
    if value is None:
        return na
    try:
        if math.isnan(float(value)):
            return na
        return format(value, fmt_str)
    except (TypeError, ValueError):
        return na


def print_table_header(col_specs: list[tuple[str, str, int, str]]) -> str:
    """Print a header + separator line for the given column spec.

    col_specs: list of (key, label, width, align) where align is "<" or ">".
    Returns the separator string so callers can reprint it between groups.
    """
    header = " ".join(
        f"{label:{align}{width}}" for _, label, width, align in col_specs
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    return sep


def print_table_row(
    col_specs: list[tuple[str, str, int, str]], values: dict, note: str = ""
) -> None:
    """Print one row using the same column spec passed to `print_table_header`."""
    parts = [
        f"{values.get(key, ''):{align}{width}}" for key, _, width, align in col_specs
    ]
    print(" ".join(parts) + note)
