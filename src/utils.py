"""Common helper utilities: text cleanup, formatting, safe file names."""

from __future__ import annotations

import re
from datetime import datetime


def normalize_column_name(name: str) -> str:
    """Return a normalized, snake_case-friendly version of a column name."""
    cleaned = str(name).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "", cleaned)
    return cleaned.lower()


def clean_text(value) -> str:
    """Trim surrounding whitespace and collapse internal whitespace."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def safe_file_name(name: str, extension: str = "") -> str:
    """Build a filesystem-safe file name, optionally adding an extension."""
    base = re.sub(r"[^0-9a-zA-Z_\-]+", "_", str(name).strip()).strip("_")
    if not base:
        base = "audit"
    base = base[:80]
    if extension and not extension.startswith("."):
        extension = "." + extension
    return f"{base}{extension}"


def timestamp_slug() -> str:
    """Return a compact timestamp usable inside file names."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def human_readable_timestamp() -> str:
    """Return a friendly timestamp for display and reports."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_percent(value: float, decimals: int = 1) -> str:
    """Format a 0-100 value as a percentage string."""
    try:
        return f"{float(value):.{decimals}f}%"
    except (TypeError, ValueError):
        return "0.0%"


def format_number(value, decimals: int = 2) -> str:
    """Format a numeric value with thousands separators."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num == int(num):
        return f"{int(num):,}"
    return f"{num:,.{decimals}f}"


def truncate(text: str, length: int = 60) -> str:
    """Truncate long text for compact display."""
    text = str(text)
    return text if len(text) <= length else text[: length - 1] + "…"
