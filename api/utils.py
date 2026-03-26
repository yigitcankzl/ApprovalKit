"""Shared utility functions."""
from datetime import time


def parse_time(t: str | None) -> time | None:
    """Parse 'HH:MM' string to time object."""
    if not t:
        return None
    parts = t.split(":")
    return time(int(parts[0]), int(parts[1]))
