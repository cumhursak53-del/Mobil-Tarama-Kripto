"""Canli gecis aday raporu — yalnizca 24s bitmis sinyal analizine dayanir. Emir acmaz."""
from __future__ import annotations

from collections import defaultdict

MIN_BITEN_SHOW = 5
MIN_BITEN_ADAY = 30
MIN_GUN_ADAY = 2
MIN_BASARI_ADAY = 55.0
MAX_SL_ORANI_ADAY = 50.0
DISLA_BASARI = 40.0
DISLA_PNL = -500.0


def _strategy_side(strategy: str, sides: list[str]) -> str:
    name = str(strategy or "").upper()
    if "_LONG" in name or "LONG]" in name:
        return "LONG"
    if "_SHORT" in name or "SHORT]" in name:
        return "SHORT"
    if not sides:
        return "?"
    buy = sum(1 for s in sides if str(s).upper() == "BUY")
    sell = len(sides) - buy
    if buy > sell:
        return "LONG"
    if sell > buy:
        return "SHORT"
    return "?"


def _status(n: int, correct: int, wrong: int, sl: int, pnl: float, days: int) -> tuple[str, str]:
    judged = correct + wrong
    if n < MIN_BITEN_SHOW:
        return "Yetersiz veri", f"En az {MIN_BITEN_SHOW} biten sinyal gerekli (simdi {n})."
    rate = 100.0 * correct / judged if judged else 0.0
    sl_pct = 100.0 * sl / n if n else 0.0
    if judged and rate < DISLA_BASARI and n >= 15:
        return "Disla", f"Basari %{rate:.0f} — canli icin cok dusuk."
    if pnl <= DISLA_PNL and n >= 15:
        return "Disla", f"Biten kâğıt PnL ${pnl:+.0f} — net zarar."
    if (
        n >= MIN_BITEN_ADAY
        and days >= MIN_GUN_ADAY
        and judged
        and rate >= MIN_BASARI_ADAY
        and pnl > 0
        and sl_pct <= MAX_SL_ORANI_ADAY
    ):
        return "Canli aday", (
            f"{n} biten, {days} gun, basari %{rate:.0f}, PnL ${pnl:+.0f}, SL orani %{sl_pct:.0f}."
        )
    notes = []
    if n < MIN_BITEN_ADAY:
        notes.append(f"biten {n}/{MIN_BITEN_ADAY}")
    if days < MIN_GUN_ADAY:
        notes.append(f"gun {days}/{MIN_GUN_ADAY}")
    if judged and rate < MIN_BASARI_ADAY:
        notes.append(f"basari %{rate:.0f} (hedef >={MIN_BASARI_ADAY:.0f})")
    if pnl <= 0:
        notes.append(f"PnL ${pnl:+.0f}")
    if sl_pct > MAX_SL_ORANI_ADAY:
        notes.append(f"SL orani %{sl_pct:.0f}")
    return "Izle", "; ".join(notes) if notes else "Esikler tamamlanmadi."


def build_live_transition_report(outcome_log: list | None) -> dict:
    by: dict[str, dict] = defaultdict(
        lambda: {
            "n": 0,
            "correct": 0,
            "wrong": 0,
            "neutral": 0,
            "tp": 0,
            "sl": 0,
            "pnl": 0.0,
            "mfe": 0.0,
            "days": set(),
            "sides": [],
            "kasa": set(),
        }
    )
    for item in outcome_log or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("strategy") or "?")
        row = by[key]
        row["n"] += 1
        verdict = item.get("verdict")
        if verdict == "correct":
            row["correct"] += 1
        elif verdict == "wrong":
            row["wrong"] += 1
        else:
            row["neutral"] += 1
        if item.get("hit_tp"):
            row["tp"] += 1
        if item.get("hit_sl"):
            row["sl"] += 1
        row["pnl"] += float(item.get("pnl_hypo_usd") or 0)
        row["mfe"] += float(item.get("mfe_r") or 0)
        row["days"].add(str(item.get("signal_time") or "")[:10])
        row["sides"].append(str(item.get("side") or ""))
        kasa = item.get("source_ledger") or item.get("ledger")
        if kasa:
            row["kasa"].add(str(kasa))

    rows = []
    for strategy, row in by.items():
        n = row["n"]
        side = _strategy_side(strategy, row["sides"])
        days = len({d for d in row["days"] if d})
        judged = row["correct"] + row["wrong"]
        rate = round(100 * row["correct"] / judged, 1) if judged else None
        sl_pct = round(100 * row["sl"] / n, 1) if n else None
        status, note = _status(n, row["correct"], row["wrong"], row["sl"], row["pnl"], days)
        rows.append({
            "Yon": side,
            "Strateji": strategy,
            "Kasa": ", ".join(sorted(row["kasa"])) or "-",
            "Biten": n,
            "Gun": days,
            "Dogru": row["correct"],
            "Yanlis": row["wrong"],
            "Notr": row["neutral"],
            "Basari_pct": rate,
            "TP": row["tp"],
            "SL": row["sl"],
            "SL_orani_pct": sl_pct,
            "Ort_MFE_R": round(row["mfe"] / n, 2) if n else None,
            "Biten_PnL": round(row["pnl"], 2),
            "Durum": status,
            "Not": note,
        })

    long_rows = [r for r in rows if r["Yon"] == "LONG"]
    short_rows = [r for r in rows if r["Yon"] == "SHORT"]
    other_rows = [r for r in rows if r["Yon"] not in ("LONG", "SHORT")]
    order = {"Canli aday": 0, "Izle": 1, "Yetersiz veri": 2, "Disla": 3}

    def sort_key(r: dict) -> tuple:
        return (order.get(r["Durum"], 9), -(r["Basari_pct"] or 0), -r["Biten"])

    long_rows.sort(key=sort_key)
    short_rows.sort(key=sort_key)
    other_rows.sort(key=sort_key)

    aday_long = sum(1 for r in long_rows if r["Durum"] == "Canli aday")
    aday_short = sum(1 for r in short_rows if r["Durum"] == "Canli aday")
    total_biten = sum(r["Biten"] for r in rows)
    day_set = set()
    for item in outcome_log or []:
        if isinstance(item, dict):
            day_set.add(str(item.get("signal_time") or "")[:10])
    day_set.discard("")
    caption = (
        f"Biten sinyal: {total_biten} | Takvim: {len(day_set)} gun | "
        f"Canli aday: {aday_long} long, {aday_short} short | "
        "Emir kapali — yalnizca secim raporu."
    )
    return {
        "long_rows": long_rows,
        "short_rows": short_rows,
        "other_rows": other_rows,
        "caption": caption,
        "total_biten": total_biten,
        "day_count": len(day_set),
        "aday_long": aday_long,
        "aday_short": aday_short,
    }
