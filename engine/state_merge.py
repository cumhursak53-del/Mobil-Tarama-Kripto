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


def history_key(h: dict) -> tuple:
    sym = str(h.get("symbol") or "")
    exit_t = str(h.get("exit_time") or "")[:19]
    if sym and exit_t:
        return (
            str(h.get("ledger") or ""),
            sym,
            exit_t,
            str(h.get("entry_time") or "")[:19],
            round(float(h.get("entry") or 0), 10),
            round(float(h.get("exit") or 0), 10),
            str(h.get("close_reason") or ""),
        )
    return (
        "incomplete",
        str(h.get("ledger") or ""),
        sym,
        exit_t,
        round(float(h.get("pnl") or 0), 8),
        str(h.get("close_reason") or ""),
    )


def merge_history(*histories: list | None) -> list[dict]:
    """Deploy/sync yarismasinda kaybolan kapanis kayitlarini birlestir."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for hist in histories:
        for h in hist or []:
            if not isinstance(h, dict):
                continue
            key = history_key(h)
            if key in seen:
                continue
            seen.add(key)
            out.append(h)
    out.sort(key=lambda x: str(x.get("exit_time") or ""))
    return out


def merge_trading_state(local: Optional[dict], remote: Optional[dict]) -> tuple[Optional[dict], str]:
    """Canli state + birlestirilmis islem gecmisi."""
    from engine.post_exit import merge_post_exit_log, merge_watchlist

    base, src = pick_best_state(local, remote)
    if not base:
        return None, "empty"
    merged = dict(base)
    merged["history"] = merge_history(
        (local or {}).get("history"),
        (remote or {}).get("history"),
        base.get("history"),
    )
    merged["post_exit_log"] = merge_post_exit_log(
        (local or {}).get("post_exit_log"),
        (remote or {}).get("post_exit_log"),
        base.get("post_exit_log"),
    )
    merged["post_exit_watchlist"] = merge_watchlist(
        (local or {}).get("post_exit_watchlist"),
        (remote or {}).get("post_exit_watchlist"),
        base.get("post_exit_watchlist"),
    )
    if merged["history"]:
        merged["closed_pnl_total"] = sum(float(h.get("pnl") or 0) for h in merged["history"])
    return merged, src


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
