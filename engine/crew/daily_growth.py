from __future__ import annotations

from engine.config import KASA_START_USD
from engine.crew.config import CREW_DAILY_GROWTH_TARGET_PCT


def _parse_day(value) -> str | None:
    if value is None or value == "":
        return None
    try:
        import pandas as pd

        return pd.to_datetime(value).date().isoformat()
    except Exception:
        s = str(value)[:10]
        return s if len(s) == 10 else None


def compute_daily_growth_metrics(
    trades: list[dict] | None,
    *,
    start_usd: float | None = None,
    target_pct: float | None = None,
) -> dict:
    """Backtest trade listesinden gunluk kasa buyume metrikleri."""
    start = float(start_usd if start_usd is not None else KASA_START_USD)
    target = float(target_pct if target_pct is not None else CREW_DAILY_GROWTH_TARGET_PCT)
    buckets: dict[str, float] = {}
    for t in trades or []:
        if not isinstance(t, dict):
            continue
        day = _parse_day(t.get("time"))
        if not day:
            continue
        buckets[day] = buckets.get(day, 0.0) + float(t.get("pnl") or 0)

    daily_pcts = {d: (pnl / start * 100.0) if start > 0 else 0.0 for d, pnl in buckets.items()}
    best_day_pct = max(daily_pcts.values()) if daily_pcts else 0.0
    days_ge_target = sum(1 for p in daily_pcts.values() if p >= target)
    top3 = sorted(daily_pcts.values(), reverse=True)[:3]
    avg_top3 = sum(top3) / len(top3) if top3 else 0.0
    return {
        "best_day_pct": round(best_day_pct, 2),
        "days_ge_target": days_ge_target,
        "avg_top3_day_pct": round(avg_top3, 2),
        "trading_days": len(daily_pcts),
        "total_pnl": round(sum(buckets.values()), 2),
        "daily_pnl": {k: round(v, 2) for k, v in sorted(buckets.items())},
        "daily_pct": {k: round(v, 2) for k, v in sorted(daily_pcts.items())},
        "meets_target": best_day_pct >= target,
    }


def growth_gate(metrics: dict, *, wf_passed: bool, target_pct: float | None = None) -> dict:
    target = float(target_pct if target_pct is not None else CREW_DAILY_GROWTH_TARGET_PCT)
    test_best = float(metrics.get("test_best_day_pct") or metrics.get("best_day_pct") or 0)
    growth_ok = test_best >= target
    passed = growth_ok and bool(wf_passed)
    reason = "passed"
    if not wf_passed:
        reason = "wf_fail"
    elif not growth_ok:
        reason = "growth_fail"
    return {
        "passed": passed,
        "reason": reason,
        "test_best_day_pct": test_best,
        "target_pct": target,
    }
