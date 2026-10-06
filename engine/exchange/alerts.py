"""Risk uyarilari. Notifier tanimliysa iletir; yoksa yalnizca kayit tutar."""
from __future__ import annotations

from typing import Callable

_alerts: list[str] = []
_notifier: Callable[[str], None] | None = None


def set_notifier(fn: Callable[[str], None] | None) -> None:
    global _notifier
    _notifier = fn


def raise_alert(message: str) -> None:
    text = str(message)
    _alerts.append(text)
    line = text if text.startswith("ALARM") else f"ALARM {text}"
    print(line, flush=True)
    if _notifier is None:
        return
    try:
        _notifier(text)
    except Exception as exc:
        print(f"ALARM notifier hatasi: {exc}", flush=True)


def recent_alerts() -> list[str]:
    return list(_alerts)


def clear_alerts() -> None:
    _alerts.clear()
