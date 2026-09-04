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


def _richness(raw: Optional[dict]) -> tuple[int, int, float]:
    """Once acik pozisyon + gecmis, sonra zaman. Deploy sifirlamasini onler."""
    if not raw:
        return 0, 0, 0.0
    pos = len(raw.get("active_positions") or {})
    hist = len(raw.get("history") or {})
    ts = _parse_ts(raw.get("updated_at"))
    return pos, hist, ts


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


def pick_best_state(local: Optional[dict], remote: Optional[dict]) -> tuple[Optional[dict], str]:
    """Deploy sonrasi bos yerel state'in dolu GitHub state'ini ezmesini engeller."""
    if not local and not remote:
        return None, "empty"
    if not local:
        return remote, "github"
    if not remote:
        return local, "local"
    lr = _richness(local)
    rr = _richness(remote)
    if rr > lr:
        return remote, "github"
    if lr > rr:
        return local, "local"
    newer = pick_newer_state(local, remote)
    if newer is remote:
        return remote, "github"
    return local, "local"
