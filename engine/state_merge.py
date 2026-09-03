from __future__ import annotations

from typing import Optional


def _parse_ts(raw: Optional[str]) -> float:
    if not raw:
        return 0.0
    try:
        from datetime import datetime
        from engine.config import TR_TZ

        return datetime.strptime(str(raw)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TR_TZ).timestamp()
    except Exception:
        return 0.0


def _state_score(raw: Optional[dict]) -> tuple[float, float]:
    if not raw:
        return 0.0, 0.0
    ts = _parse_ts(raw.get("updated_at"))
    try:
        eq = float(raw.get("equity") or 0)
    except (TypeError, ValueError):
        eq = 0.0
    if eq <= 0:
        ledgers = raw.get("ledgers") or {}
        try:
            eq = sum(float(v) for v in ledgers.values())
        except (TypeError, ValueError):
            eq = 0.0
    hist = raw.get("history") or []
    return ts, eq + len(hist) * 0.001


def pick_newer_state(local: Optional[dict], remote: Optional[dict]) -> Optional[dict]:
    if local and not remote:
        return local
    if remote and not local:
        return remote
    if not local and not remote:
        return None
    lt, le = _state_score(local)
    rt, re = _state_score(remote)
    if rt > lt:
        return remote
    if lt > rt:
        return local
    if re >= le:
        return remote
    return local
