from __future__ import annotations

from typing import Optional

import pandas as pd

from engine.config import (
    SMC_MIN_CONFLUENCE,
    SMC_MIN_GRADE,
    SMC_MIN_TRADE_SCORE,
    SMC_REQUIRE_CANDLE_CONFIRM,
    SMC_REQUIRE_KILLZONE,
    SMC_REQUIRE_OB_FVG,
)
from structure.smc import SMCAnalysis

SMC_LEDGER = "Kasa_SMC"
_GRADE_RANK = {"A": 3, "B": 2, "C": 1, "none": 0}


def _grade_ok(grade: str) -> bool:
    return _GRADE_RANK.get(str(grade), 0) >= _GRADE_RANK.get(SMC_MIN_GRADE, 2)


def _has_trigger(notes: str, *needles: str) -> bool:
    return any(n in notes for n in needles)


def _notes_text(val) -> str:
    if isinstance(val, list):
        return " ".join(str(x) for x in val)
    return str(val or "")


def _analysis_from_row(row: dict) -> SMCAnalysis:
    a = SMCAnalysis()
    scalar = (
        "trend", "last_event", "internal_event", "external_event",
        "hierarchy_long", "hierarchy_short", "session", "killzone",
        "confluence_long", "confluence_short", "setup_grade_long", "setup_grade_short",
        "ob_fvg_valid_long", "ob_fvg_valid_short", "long_score", "short_score",
    )
    for k in scalar:
        if k in row:
            setattr(a, k, row[k])
    ln = row.get("long_notes")
    sn = row.get("short_notes")
    if isinstance(ln, str):
        a.long_notes = [x.strip() for x in ln.split("|") if x.strip()]
    elif isinstance(ln, list):
        a.long_notes = ln
    if isinstance(sn, str):
        a.short_notes = [x.strip() for x in sn.split("|") if x.strip()]
    elif isinstance(sn, list):
        a.short_notes = sn
    return a


def smc_block_reason(row: dict) -> tuple[Optional[str], str]:
    """Scan satirindan islem yonu ve engel nedenini dondur."""
    from engine.smc_scan import smc_trade_side

    ls = int(row.get("long_score") or 0)
    ss = int(row.get("short_score") or 0)
    notes_l = _notes_text(row.get("long_notes"))
    notes_s = _notes_text(row.get("short_notes"))

    side_obj = smc_trade_side(_analysis_from_row(row))
    side = side_obj.value if side_obj else None
    if side is not None:
        return side, "TRADE_OK"

    best_side = "BUY" if ls >= ss else "SELL"
    score = ls if best_side == "BUY" else ss
    grade = row.get("setup_grade_long") if best_side == "BUY" else row.get("setup_grade_short")
    conf = int((row.get("confluence_long") if best_side == "BUY" else row.get("confluence_short")) or 0)
    notes = notes_l if best_side == "BUY" else notes_s

    if score < SMC_MIN_TRADE_SCORE:
        return None, f"skor<{SMC_MIN_TRADE_SCORE}"
    if best_side == "BUY" and ls <= ss:
        return None, "long<=short"
    if best_side == "SELL" and ss <= ls:
        return None, "short<=long"
    if not _has_trigger(notes, "OB_retest", "BOS", "breaker_retest", "ext_BOS", "int_BOS", "IFVG", "inducement"):
        return None, "tetik_yok"
    if best_side == "BUY" and not row.get("hierarchy_long"):
        return None, "hierarchy_long"
    if best_side == "SELL" and not row.get("hierarchy_short"):
        return None, "hierarchy_short"
    if conf < SMC_MIN_CONFLUENCE:
        return None, f"confluence<{SMC_MIN_CONFLUENCE}"
    if not _grade_ok(str(grade)):
        return None, f"grade<{SMC_MIN_GRADE}"
    if SMC_REQUIRE_KILLZONE and row.get("session") not in ("london_open", "ny_open", "london_close", "asia"):
        if "killzone:" not in notes:
            return None, "killzone"
    if SMC_REQUIRE_OB_FVG:
        if best_side == "BUY" and not row.get("ob_fvg_valid_long"):
            return None, "ob_fvg_long"
        if best_side == "SELL" and not row.get("ob_fvg_valid_short"):
            return None, "ob_fvg_short"
    if SMC_REQUIRE_CANDLE_CONFIRM and "candle_confirm" not in notes:
        return None, "candle_confirm"
    if best_side == "BUY" and row.get("external_event") == "choch_bear":
        return None, "choch_bear"
    if best_side == "SELL" and row.get("external_event") == "choch_bull":
        return None, "choch_bull"
    if best_side == "BUY" and row.get("trend") == "bear" and row.get("internal_event") == "choch_bear":
        return None, "ic_choch_bear"
    if best_side == "SELL" and row.get("trend") == "bull" and row.get("internal_event") == "choch_bull":
        return None, "ic_choch_bull"
    return None, "diger"


def smc_diagnostics_rows(
    scan: dict,
    *,
    pending: list | None = None,
    active: dict | None = None,
) -> pd.DataFrame:
    """SMC tarama verisinden islem adaylari ve engel nedenleri."""
    pending_syms = {p.get("symbol") for p in (pending or []) if p.get("ledger") == SMC_LEDGER}
    open_syms = {
        p.get("symbol")
        for p in (active or {}).values()
        if isinstance(p, dict) and p.get("ledger_name") == SMC_LEDGER
    }
    rows = []
    for sym, raw in (scan or {}).items():
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        row["symbol"] = sym
        side, reason = smc_block_reason(row)
        rows.append({
            "Sembol": sym,
            "Long_skoru": row.get("long_score", 0),
            "Short_skoru": row.get("short_score", 0),
            "Islem_yonu": side or "-",
            "Durum": reason,
            "Long_grade": row.get("setup_grade_long", "-"),
            "Short_grade": row.get("setup_grade_short", "-"),
            "Long_conf": row.get("confluence_long", 0),
            "Short_conf": row.get("confluence_short", 0),
            "Session": row.get("session", "-"),
            "Bekleyen_limit": "E" if sym in pending_syms else "-",
            "Acik_pozisyon": "E" if sym in open_syms else "-",
            "Guncelleme": row.get("updated_at", "-"),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    order = {"TRADE_OK": 0}
    df["_ord"] = df["Durum"].map(lambda x: order.get(x, 1))
    return df.sort_values(["_ord", "Long_skoru", "Short_skoru"], ascending=[True, False, False]).drop(columns="_ord")


def smc_summary_stats(scan: dict, pending: list | None = None, active: dict | None = None) -> dict:
    df = smc_diagnostics_rows(scan, pending=pending, active=active)
    if df.empty:
        return {"taranan": 0, "trade_ok": 0, "pending": 0, "acik": 0, "engel": {}}
    engel = df[df["Durum"] != "TRADE_OK"]["Durum"].value_counts().to_dict()
    return {
        "taranan": len(df),
        "trade_ok": int((df["Durum"] == "TRADE_OK").sum()),
        "pending": int((df["Bekleyen_limit"] == "E").sum()),
        "acik": int((df["Acik_pozisyon"] == "E").sum()),
        "engel": engel,
    }
