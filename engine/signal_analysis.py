"""24s sinyal sonuc analizi — hipotetik SL/TP ve yon dogrulugu."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from engine.trade_analysis import _filter_bars, _parse_ts_ms, _pnl_usd, _r_multiple
from engine.types import Side


def make_signal_id(symbol: str, strategy: str, side: str, signal_time: str) -> str:
    return f"{symbol}|{strategy}|{side}|{signal_time}"


def signal_pnl_view(watch: dict, price: float | None = None) -> dict:
    """Aktif izleme: fiyat yuzdesi, 10x ROE ve USD kar/zarar."""
    from engine.config import MIN_LEVERAGE

    entry = float(watch.get("entry") or 0)
    side = str(watch.get("side") or Side.BUY.value)
    last = float(price if price is not None else watch.get("last_price") or entry)
    move = signal_move_pct(entry, last, side)
    leverage = max(float(watch.get("leverage") or MIN_LEVERAGE or 10), 1.0)
    notional = float(watch.get("notional") or 100.0)
    if not watch.get("notional_levered"):
        notional *= leverage
    return {
        "move_pct": move,
        "leverage": leverage,
        "roe_pct": round(move * leverage, 2),
        "pnl_usd": round(notional * (move / 100.0), 2),
    }


def signal_move_pct(entry: float, last_price: float, side: str) -> float:
    """Giris fiyatina gore anlik kar/zarar yuzdesi (+ kar, - zarar)."""
    entry = float(entry or 0)
    if entry <= 0:
        return 0.0
    move = (float(last_price or entry) - entry) / entry * 100.0
    if str(side).upper() == Side.SELL.value:
        move = -move
    return round(move, 2)


def _hit_tp(side: str, hi: float, lo: float, tp: float) -> bool:
    if tp <= 0:
        return False
    return hi >= tp if side == Side.BUY.value else lo <= tp


def _hit_sl(side: str, hi: float, lo: float, sl: float) -> bool:
    if sl <= 0:
        return False
    return lo <= sl if side == Side.BUY.value else hi >= sl


def analyze_completed_signal(watch: dict, klines: pd.DataFrame | None = None) -> dict:
    """24s izleme biten sinyali analiz et (gercek islem acilmamis olabilir)."""
    entry = float(watch.get("entry") or 0)
    side = str(watch.get("side") or Side.BUY.value)
    sl = float(watch.get("sl_price") or 0)
    tp_raw = watch.get("tp_price")
    tp = float(tp_raw) if tp_raw not in (None, "") else None
    strength = float(watch.get("strength") or 1.0)
    from engine.config import MIN_LEVERAGE

    leverage = float(watch.get("leverage") or MIN_LEVERAGE or 10)
    leverage = max(leverage, 1.0)
    notional = float(watch.get("notional") or 100.0)
    if not watch.get("notional_levered"):
        notional *= leverage

    post_high = float(watch.get("post_high") or entry)
    post_low = float(watch.get("post_low") or entry)
    last_price = float(watch.get("last_price") or entry)

    signal_ms = _parse_ts_ms(watch.get("signal_time", ""))
    until_ms = _parse_ts_ms(watch.get("watch_until", ""))

    bars = _filter_bars(klines, signal_ms, until_ms or signal_ms + 86_400_000)
    if not bars.empty:
        hi = float(bars["high"].max())
        lo = float(bars["low"].min())
        post_high = max(post_high, hi)
        post_low = min(post_low, lo)

    if side == Side.BUY.value:
        mfe_price = post_high
        mae_price = post_low
    else:
        mfe_price = post_low
        mae_price = post_high

    risk_usd = abs(entry - sl) / entry * notional if entry > 0 and sl > 0 else notional * 0.01
    mfe_usd = max(0.0, _pnl_usd(entry, mfe_price, side, notional))
    mae_usd = max(0.0, -_pnl_usd(entry, mae_price, side, notional))
    pnl_at_24h = _pnl_usd(entry, last_price, side, notional)

    hit_tp = bool(tp and _hit_tp(side, post_high, post_low, tp))
    hit_sl = bool(sl and _hit_sl(side, post_high, post_low, sl))

    move_pct = signal_move_pct(entry, last_price, side)

    recommendations: list[str] = []
    if hit_tp and not hit_sl:
        outcome = "tp_hit"
        verdict = "correct"
        recommendations.append("Sinyal dogru: 24s icinde TP seviyesine ulasildi.")
    elif hit_sl and not hit_tp:
        outcome = "sl_hit"
        verdict = "wrong"
        recommendations.append("Sinyal zayif: 24s icinde SL tetiklendi, yon tutmadi.")
    elif hit_sl and hit_tp:
        outcome = "sl_before_tp" if mae_usd > mfe_usd else "tp_before_sl"
        verdict = "wrong" if outcome == "sl_before_tp" else "correct"
        recommendations.append(
            "Kararsiz: hem SL hem TP bolgesi goruldu — giris zamanlamasi gozden gecir."
        )
    elif move_pct >= 0.5:
        outcome = "direction_ok"
        verdict = "correct"
        recommendations.append(f"Yon dogru: 24s sonunda ~{move_pct:+.2f}% lehte hareket.")
    elif move_pct <= -0.5:
        outcome = "direction_wrong"
        verdict = "wrong"
        recommendations.append(f"Yon yanlis: 24s sonunda ~{move_pct:+.2f}% aleyhe hareket.")
    else:
        outcome = "neutral"
        verdict = "neutral"
        recommendations.append("Notr: 24s icinde belirgin yon hareketi yok.")

    if verdict == "correct" and tp and not hit_tp and _r_multiple(mfe_usd, risk_usd) >= 1.5:
        recommendations.append(
            f"TP uzak olabilir: MFE ~{_r_multiple(mfe_usd, risk_usd):.1f}R ama TP'ye ulasilmadi."
        )
    if verdict == "wrong" and _r_multiple(mfe_usd, risk_usd) >= 1.0:
        recommendations.append(
            f"Erken/tekrar sinyal: 24s icinde ~{_r_multiple(mfe_usd, risk_usd):.1f}R lehte hareket oldu."
        )

    return {
        "signal_id": watch.get("signal_id"),
        "symbol": watch.get("symbol"),
        "side": side,
        "ledger": watch.get("ledger"),
        "strategy": watch.get("strategy"),
        "source_ledger": watch.get("source_ledger"),
        "entry": entry,
        "sl_price": sl,
        "tp_price": tp,
        "strength": strength,
        "signal_time": watch.get("signal_time"),
        "watch_until": watch.get("watch_until"),
        "price_at_24h": last_price,
        "move_pct": round(move_pct, 3),
        "leverage": leverage,
        "roe_pct": round(move_pct * leverage, 3),
        "hit_tp": hit_tp,
        "hit_sl": hit_sl,
        "outcome": outcome,
        "verdict": verdict,
        "mfe_r": round(_r_multiple(mfe_usd, risk_usd), 2),
        "mae_r": round(_r_multiple(mae_usd, risk_usd), 2),
        "pnl_hypo_usd": round(pnl_at_24h, 2),
        "risk_usd": round(risk_usd, 2),
        "recommendations": recommendations,
        "analyzed_at": watch.get("analyzed_at"),
        "coin_chg_24h": watch.get("coin_chg_24h"),
        "btc_chg_24h": watch.get("btc_chg_24h"),
        "btc_rel_ratio": watch.get("btc_rel_ratio"),
    }


def strategy_signal_summary(analyses: list[dict]) -> pd.DataFrame:
    if not analyses:
        return pd.DataFrame()
    rows = []
    by_strat: dict[str, list] = {}
    for a in analyses:
        key = str(a.get("strategy") or "unknown")
        by_strat.setdefault(key, []).append(a)
    for strategy, items in by_strat.items():
        n = len(items)
        correct = sum(1 for x in items if x.get("verdict") == "correct")
        wrong = sum(1 for x in items if x.get("verdict") == "wrong")
        tp_hit = sum(1 for x in items if x.get("outcome") == "tp_hit")
        sl_hit = sum(1 for x in items if x.get("outcome") in ("sl_hit", "sl_before_tp"))
        avg_mfe = sum(float(x.get("mfe_r") or 0) for x in items) / n
        note = ""
        if n >= 3 and wrong >= max(2, n // 2):
            note = "Yuksek hata — kosullari sikilastir"
        elif n >= 3 and correct >= max(2, (2 * n) // 3):
            note = "Guclu sinyal profili"
        rows.append({
            "Strateji": strategy,
            "Analiz": n,
            "Dogru": correct,
            "Yanlis": wrong,
            "TP_vurdu": tp_hit,
            "SL_vurdu": sl_hit,
            "Ort_MFE_R": round(avg_mfe, 2),
            "Basari_pct": round(100 * correct / n, 1) if n else 0,
            "Oneri": note,
        })
    return pd.DataFrame(rows).sort_values("Analiz", ascending=False)
