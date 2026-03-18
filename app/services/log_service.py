"""Log service — reads application log files."""

import os
from datetime import datetime

from flask import current_app

# Allowlist of log file base names (without .log extension)
ALLOWED_LOG_NAMES = {"app", "auth"}


def _get_log_dir():
    """Return the configured log directory path."""
    return current_app.config.get("LOG_DIR", os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
    ))


def _validate_log_name(log_name):
    """Validate that a log name is in the allowlist.

    Prevents path traversal by rejecting any name not in the allowlist.

    Returns:
        True if the name is valid, False otherwise.
    """
    if not log_name or not isinstance(log_name, str):
        return False
    # Reject anything with path separators or parent traversal
    if "/" in log_name or "\\" in log_name or ".." in log_name:
        return False
    return log_name in ALLOWED_LOG_NAMES


def get_available_logs():
    """Return list of available log files with metadata.

    Returns:
        list of dicts with keys: name, path, size, modified, exists
    """
    log_dir = _get_log_dir()
    logs = []
    for name in sorted(ALLOWED_LOG_NAMES):
        filepath = os.path.join(log_dir, f"{name}.log")
        entry = {
            "name": name,
            "path": filepath,
            "exists": os.path.isfile(filepath),
            "size": 0,
            "modified": None,
        }
        if entry["exists"]:
            stat = os.stat(filepath)
            entry["size"] = stat.st_size
            entry["modified"] = datetime.fromtimestamp(stat.st_mtime)
        logs.append(entry)
    return logs


def read_log(log_name, lines=200, offset=0):
    """Read the last N lines from a log file.

    Args:
        log_name: Name of the log file (e.g., 'app', 'auth')
        lines: Number of lines to return (default 200, max 1000)
        offset: Line offset for pagination (0 = latest lines)

    Returns:
        dict with 'lines' (list of strings), 'total_lines' (int),
        'log_name' (str), 'error' (str or None)
    """
    if not _validate_log_name(log_name):
        return {
            "lines": [],
            "total_lines": 0,
            "log_name": log_name,
            "error": f"Invalid log name: {log_name}",
        }

    # Cap lines at 1000
    lines = min(max(1, int(lines)), 1000)
    offset = max(0, int(offset))

    log_dir = _get_log_dir()
    filepath = os.path.join(log_dir, f"{log_name}.log")

    if not os.path.isfile(filepath):
        return {
            "lines": [],
            "total_lines": 0,
            "log_name": log_name,
            "error": None,
        }

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except OSError as e:
        return {
            "lines": [],
            "total_lines": 0,
            "log_name": log_name,
            "error": f"Error reading log: {e}",
        }

    total = len(all_lines)

    if offset == 0:
        # Return the last N lines (most recent)
        selected = all_lines[-lines:] if lines < total else all_lines
    else:
        # Offset from the end
        end = max(total - offset, 0)
        start = max(end - lines, 0)
        selected = all_lines[start:end]

    # Strip trailing newlines for cleaner display
    selected = [line.rstrip("\n").rstrip("\r") for line in selected]

    return {
        "lines": selected,
        "total_lines": total,
        "log_name": log_name,
        "error": None,
    }
