from __future__ import annotations

from typing import Optional

import pandas as pd

from engine.types import Side


def make_trade_id(ledger: str, symbol: str, entry_time: str) -> str:
    return f"{ledger}|{symbol}|{entry_time}"


def _risk_usd(entry: float, initial_sl: float, notional: float) -> float:
    if entry <= 0 or notional <= 0:
        return 0.0
    sl = initial_sl if initial_sl else entry * 0.99
    return abs(entry - sl) / entry * notional


def _pnl_usd(entry: float, price: float, side: str, notional: float) -> float:
    if entry <= 0 or notional <= 0:
        return 0.0
    ratio = (price - entry) / entry if side == Side.BUY.value else (entry - price) / entry
    return notional * ratio


def _r_multiple(pnl_usd: float, risk_usd: float) -> float:
    return pnl_usd / risk_usd if risk_usd else 0.0


def _filter_bars(df: pd.DataFrame | None, start_ms: float, end_ms: float) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.reset_index()
    if "close_time" not in out.columns:
        return pd.DataFrame()
    ts = pd.to_datetime(out["close_time"], utc=True).astype("int64") // 10**6
    mask = (ts >= start_ms) & (ts <= end_ms)
    return out.loc[mask]


def _parse_ts_ms(value: str) -> float:
    if not value:
        return 0.0
    try:
        from datetime import datetime
        from engine.config import TR_TZ

        dt = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TR_TZ)
        return dt.timestamp() * 1000
    except Exception:
        return 0.0


def analyze_completed_watch(watch: dict, klines: pd.DataFrame | None = None) -> dict:
    """Tamamlanan post-exit izleme kaydini analiz et."""
    entry = float(watch.get("entry") or 0)
    exit_px = float(watch.get("exit") or 0)
    side = str(watch.get("side") or Side.BUY.value)
    notional = float(watch.get("notional") or 0)
    initial_sl = float(watch.get("initial_sl") or watch.get("sl_price") or 0)
    tp_price = watch.get("tp_price")
    tp_price = float(tp_price) if tp_price not in (None, "") else None
    close_reason = str(watch.get("close_reason") or "")
    peak = float(watch.get("peak_price") or entry)
    post_high = float(watch.get("post_high") or exit_px)
    post_low = float(watch.get("post_low") or exit_px)
    last_price = float(watch.get("last_price") or exit_px)

    risk_usd = _risk_usd(entry, initial_sl, notional)

    entry_ms = _parse_ts_ms(watch.get("entry_time", ""))
    exit_ms = _parse_ts_ms(watch.get("exit_time", ""))
    until_ms = _parse_ts_ms(watch.get("watch_until", ""))

    in_bars = _filter_bars(klines, entry_ms, exit_ms)
    post_bars = _filter_bars(klines, exit_ms, until_ms or exit_ms + 86_400_000)

    if not in_bars.empty:
        hi = float(in_bars["high"].max())
        lo = float(in_bars["low"].min())
    else:
        hi = max(entry, exit_px, peak, post_high)
        lo = min(entry, exit_px, initial_sl or exit_px, post_low)

    if not post_bars.empty:
        post_high = max(post_high, float(post_bars["high"].max()))
        post_low = min(post_low, float(post_bars["low"].min()))

    if side == Side.BUY.value:
        mfe_in_price = hi
        mae_in_price = lo
        mfe_post_price = post_high
        mae_post_price = post_low
    else:
        mfe_in_price = lo
        mae_in_price = hi
        mfe_post_price = post_low
        mae_post_price = post_high

    mfe_in_usd = max(0.0, _pnl_usd(entry, mfe_in_price, side, notional))
    mae_in_usd = max(0.0, -_pnl_usd(entry, mae_in_price, side, notional))
    mfe_post_usd = max(0.0, _pnl_usd(exit_px, mfe_post_price, side, notional))
    mae_post_usd = max(0.0, -_pnl_usd(exit_px, mae_post_price, side, notional))

    optimal_price = mfe_in_price
    if not post_bars.empty:
        if side == Side.BUY.value:
            optimal_price = max(mfe_in_price, post_high)
        else:
            optimal_price = min(mfe_in_price, post_low)
    optimal_pnl = _pnl_usd(entry, optimal_price, side, notional)
    actual_pnl = float(watch.get("pnl") or _pnl_usd(entry, exit_px, side, notional))
    optimal_vs_actual_pct = (
        (optimal_pnl - actual_pnl) / abs(actual_pnl) * 100 if actual_pnl else 0.0
    )

    sl_verdict = ""
    tp_verdict = ""
    sl_wider_25_would_win = False
    sl_extra_loss_avoided = 0.0
    missed_upside_usd = 0.0
    recommendations: list[str] = []

    recovered_to_entry = (
        (side == Side.BUY.value and post_high >= entry)
        or (side == Side.SELL.value and post_low <= entry)
    )

    if close_reason == "SL":
        if side == Side.BUY.value:
            sl_extra_loss_avoided = max(0.0, (exit_px - post_low) / entry * notional)
            wider_sl = initial_sl - abs(entry - initial_sl) * 0.25 if initial_sl else exit_px * 0.99
            sl_wider_25_would_win = post_high >= entry and exit_px <= wider_sl
        else:
            sl_extra_loss_avoided = max(0.0, (post_high - exit_px) / entry * notional)
            wider_sl = initial_sl + abs(initial_sl - entry) * 0.25 if initial_sl else exit_px * 1.01
            sl_wider_25_would_win = post_low <= entry and exit_px >= wider_sl

        if recovered_to_entry or _r_multiple(mfe_in_usd, risk_usd) >= 1.5:
            sl_verdict = "too_tight"
            recommendations.append(
                "SL cok siki: 24s icinde fiyat girise dondu veya islem icinde >=1.5R lehte hareket oldu. "
                "SL mesafesini ~%25 artirmayi dene."
            )
        elif _r_multiple(sl_extra_loss_avoided, risk_usd) >= 0.5:
            sl_verdict = "correct"
            recommendations.append(
                f"SL dogru: Cikis sonrasi fiyat daha da aleyhe gitti (~${sl_extra_loss_avoided:.2f} ek kayip onlendi)."
            )
        else:
            sl_verdict = "neutral"
            recommendations.append("SL nötr: Belirgin geri donus veya ek dusus yok.")

    elif close_reason == "TP":
        missed_upside_usd = mfe_post_usd
        if _r_multiple(missed_upside_usd, risk_usd) >= 0.5:
            tp_verdict = "too_early"
            recommendations.append(
                f"TP erken: Cikis sonrasi +${missed_upside_usd:.2f} "
                f"(~{_r_multiple(missed_upside_usd, risk_usd):.1f}R) daha kar mumkun."
            )
        elif _r_multiple(mae_post_usd, risk_usd) >= 1.0:
            tp_verdict = "correct"
            recommendations.append(
                f"TP dogru: Sonrasinda ~{_r_multiple(mae_post_usd, risk_usd):.1f}R geri cekilme oldu."
            )
        else:
            tp_verdict = "neutral"
            recommendations.append("TP nötr: Sonraki hareket sinirli.")

    return {
        "trade_id": watch.get("trade_id"),
        "symbol": watch.get("symbol"),
        "side": side,
        "ledger": watch.get("ledger"),
        "strategy": watch.get("strategy"),
        "entry": entry,
        "exit": exit_px,
        "entry_time": watch.get("entry_time"),
        "exit_time": watch.get("exit_time"),
        "close_reason": close_reason,
        "pnl": actual_pnl,
        "risk_usd": round(risk_usd, 2),
        "mfe_in_usd": round(mfe_in_usd, 2),
        "mae_in_usd": round(mae_in_usd, 2),
        "mfe_in_r": round(_r_multiple(mfe_in_usd, risk_usd), 2),
        "mae_in_r": round(_r_multiple(mae_in_usd, risk_usd), 2),
        "mfe_post_usd": round(mfe_post_usd, 2),
        "mae_post_usd": round(mae_post_usd, 2),
        "price_at_24h": last_price,
        "optimal_tp_price": round(optimal_price, 8),
        "optimal_vs_actual_pct": round(optimal_vs_actual_pct, 2),
        "sl_verdict": sl_verdict,
        "tp_verdict": tp_verdict,
        "sl_wider_25_would_win": sl_wider_25_would_win,
        "sl_extra_loss_avoided": round(sl_extra_loss_avoided, 2),
        "missed_upside_usd": round(missed_upside_usd, 2),
        "recommendations": recommendations,
        "analyzed_at": watch.get("analyzed_at"),
    }


def ledger_analysis_summary(analyses: list[dict]) -> pd.DataFrame:
    if not analyses:
        return pd.DataFrame()
    rows = []
    by_ledger: dict[str, list] = {}
    for a in analyses:
        by_ledger.setdefault(str(a.get("ledger") or ""), []).append(a)
    for ledger, items in by_ledger.items():
        sl_items = [x for x in items if x.get("close_reason") == "SL"]
        tp_items = [x for x in items if x.get("close_reason") == "TP"]
        sl_tight = sum(1 for x in sl_items if x.get("sl_verdict") == "too_tight")
        sl_correct = sum(1 for x in sl_items if x.get("sl_verdict") == "correct")
        tp_early = sum(1 for x in tp_items if x.get("tp_verdict") == "too_early")
        tp_correct = sum(1 for x in tp_items if x.get("tp_verdict") == "correct")
        note = ""
        if sl_items and sl_tight >= max(2, len(sl_items) // 2):
            note = "SL sikligi yuksek — SL/ATR carpani gozden gecir"
        elif tp_items and tp_early >= max(2, len(tp_items) // 2):
            note = "TP erken kapanma sik — TP hedefini genislet"
        rows.append({
            "Kasa": ledger,
            "Analiz": len(items),
            "SL_siki": sl_tight,
            "SL_dogru": sl_correct,
            "TP_erken": tp_early,
            "TP_dogru": tp_correct,
            "Oneri": note,
        })
    return pd.DataFrame(rows).sort_values("Analiz", ascending=False)
