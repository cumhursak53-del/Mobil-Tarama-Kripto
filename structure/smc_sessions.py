"""SMC session / killzone — UTC saat pencereleri (kripto 7/24)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# UTC saat araliklari (baslangic dahil, bitis haric)
SESSION_WINDOWS: dict[str, tuple[int, int]] = {
    "asia": (0, 8),
    "london": (7, 16),
    "ny": (13, 22),
}

KILLZONE_WINDOWS: dict[str, tuple[int, int]] = {
    "london_open": (7, 10),
    "ny_open": (13, 16),
    "london_ny_overlap": (13, 16),
    "silver_bullet_am": (14, 15),
    "silver_bullet_pm": (19, 20),
}


def _utc_hour(ts) -> int:
    if ts is None:
        return datetime.now(timezone.utc).hour
    if hasattr(ts, "hour"):
        t = ts
        if getattr(t, "tzinfo", None) is None:
            t = t.replace(tzinfo=timezone.utc)
        else:
            t = t.astimezone(timezone.utc)
        return int(t.hour)
    return datetime.now(timezone.utc).hour


def _in_window(hour: int, start: int, end: int) -> bool:
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def active_sessions(ts=None) -> list[str]:
    hour = _utc_hour(ts)
    return [name for name, (a, b) in SESSION_WINDOWS.items() if _in_window(hour, a, b)]


def active_killzones(ts=None) -> list[str]:
    hour = _utc_hour(ts)
    return [name for name, (a, b) in KILLZONE_WINDOWS.items() if _in_window(hour, a, b)]


def in_killzone(ts=None) -> bool:
    return bool(active_killzones(ts))


def session_label(ts=None) -> str:
    zones = active_killzones(ts)
    if zones:
        return zones[0]
    sessions = active_sessions(ts)
    return sessions[0] if sessions else "off_hours"
