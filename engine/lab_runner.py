from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Optional

from engine.config import (
    GEMINI_API_KEY,
    LAB_AUTO,
    LAB_AUTO_INTERVAL_SEC,
    LAB_BACKTEST_BATCH,
    LAB_BACKTEST_UNIVERSE,
    LAB_FREEZE,
    LAB_GENERATE_LIMIT,
    LAB_MAX_CANDIDATES,
    LAB_MIN_RECIPES,
    RESEARCH_ENABLED,
)
from engine.data import fetch_all_timeframes, fetch_dominance, fetch_symbols
from engine.lab_backtest import run_lab_backtests
from engine.lab_state import load_lab_state, now_tr, promote_recipe, sync_lab_state
from engine.research_runner import run_research
from engine.strategy_generator import generate_recipes

if TYPE_CHECKING:
    from engine.portfolio import Portfolio

_lock = threading.Lock()
_running = False


def _pipeline(state: dict) -> dict:
    return state.setdefault(
        "pipeline",
        {
            "status": "idle",
            "last_run_at": "",
            "last_generate_at": "",
            "last_backtest_at": "",
            "last_message": "",
            "last_generated": 0,
            "last_backtested": 0,
            "last_promoted": 0,
            "last_researched": 0,
        },
    )


def _backtested_ids(state: dict) -> set[str]:
    return {b.get("recipe_id") for b in (state.get("backtests") or []) if b.get("recipe_id")}


def _pending_recipes(state: dict, limit: int) -> list[dict]:
    tested = _backtested_ids(state)
    out = []
    for r in state.get("recipes") or []:
        rid = r.get("id")
        if rid and rid not in tested:
            out.append(r)
        if len(out) >= limit:
            break
    return out


def _paper_slots_free(state: dict) -> int:
    active = len([c for c in state.get("candidates") or [] if c.get("status") == "paper"])
    return max(0, LAB_MAX_CANDIDATES - active)


def run_lab_pipeline(*, log=None, force: bool = False) -> dict:
    """Tarif uret + backtest + aday sec. Shell gerektirmez."""
    global _running
    if LAB_FREEZE or not LAB_AUTO:
        return {"skipped": True, "reason": "lab_frozen_or_disabled"}

    if not _lock.acquire(blocking=False):
        return {"skipped": True, "reason": "already_running"}

    _running = True
    pipe = {}
    try:
        state = load_lab_state()
        pipe = _pipeline(state)
        pipe["status"] = "running"
        pipe["last_message"] = "Lab pipeline calisiyor..."
        research_meta = state.setdefault("research", {})
        research_meta["gemini_configured"] = bool(GEMINI_API_KEY)
        research_meta["research_enabled"] = RESEARCH_ENABLED
        sync_lab_state(state)

        generated = 0
        researched = 0
        recipes = state.get("recipes") or []

        if RESEARCH_ENABLED and GEMINI_API_KEY:
            new_research = run_research(state, log=log)
        elif RESEARCH_ENABLED and log:
            log("Arastirma atlandi: GEMINI_API_KEY worker env'de tanimli degil")
            new_research = []
        else:
            new_research = []
        if new_research:
            state.setdefault("recipes", []).extend(new_research)
            researched = len(new_research)
            pipe["last_researched"] = researched
            if log:
                log(f"Arastirma: {researched} yeni tarif (YouTube/haber/Gemini)")

        need_recipes = len(state.get("recipes") or []) < LAB_MIN_RECIPES or (
            force and _paper_slots_free(state) > 0 and len(_pending_recipes(state, 1)) == 0
        )
        if need_recipes:
            new_recipes = generate_recipes(limit=LAB_GENERATE_LIMIT)
            state.setdefault("recipes", []).extend(new_recipes)
            generated = len(new_recipes)
            pipe["last_generate_at"] = now_tr()
            pipe["last_generated"] = generated
            if log:
                log(f"Lab: {generated} yeni tarif uretildi (toplam {len(state['recipes'])})")

        pending = _pending_recipes(state, LAB_BACKTEST_BATCH)
        backtested = 0
        promoted = 0
        if pending and _paper_slots_free(state) > 0:
            symbols = fetch_symbols(LAB_BACKTEST_UNIVERSE)[:LAB_BACKTEST_UNIVERSE]
            dominance = fetch_dominance()
            symbol_frames = {}
            for sym in symbols:
                try:
                    symbol_frames[sym] = fetch_all_timeframes(sym)
                    time.sleep(0.1)
                except Exception as e:
                    if log:
                        log(f"Lab veri hatasi {sym}: {e}")
            if symbol_frames:
                rows = run_lab_backtests(pending, symbol_frames, dominance)
                for row in rows:
                    m = row["metrics"]
                    state.setdefault("backtests", []).append({
                        "recipe_id": row["recipe"]["id"],
                        "metrics": m,
                        "symbols": list(symbol_frames.keys()),
                        "run_at": now_tr(),
                    })
                    backtested += 1
                    if m.get("passed") and _paper_slots_free(state) > 0:
                        cand = promote_recipe(state, row["recipe"], m)
                        if cand:
                            promoted += 1
                            if log:
                                log(f"Lab: aday secildi {cand.ledger} (tarif {cand.recipe_id})")
                pipe["last_backtest_at"] = now_tr()
                pipe["last_backtested"] = backtested
                pipe["last_promoted"] = promoted
                if log:
                    log(f"Lab backtest: {backtested} tarif, {promoted} aday paper'a alindi")

        pipe["status"] = "ok"
        pipe["last_run_at"] = now_tr()
        pipe["last_message"] = (
            f"Arastirma {researched}, uretim {generated}, backtest {backtested}, yeni aday {promoted}"
        )
        sync_lab_state(state)
        return {
            "researched": researched,
            "generated": generated,
            "backtested": backtested,
            "promoted": promoted,
            "recipe_total": len(state.get("recipes") or []),
            "paper_count": len([c for c in state.get("candidates") or [] if c.get("status") == "paper"]),
        }
    except Exception as e:
        try:
            state = load_lab_state()
            pipe = _pipeline(state)
            pipe["status"] = "error"
            pipe["last_message"] = str(e)[:200]
            pipe["last_run_at"] = now_tr()
            sync_lab_state(state)
        except Exception:
            pass
        if log:
            log(f"Lab pipeline hatasi: {e}")
        return {"error": str(e)}
    finally:
        _running = False
        _lock.release()


def maybe_run_lab_pipeline(pf: "Portfolio", force: bool = False) -> None:
    if LAB_FREEZE or not LAB_AUTO:
        return
    state = pf.lab_state or load_lab_state()
    pipe = state.get("pipeline") or {}
    if not force:
        last = pipe.get("last_run_at") or ""
        if last:
            try:
                from datetime import datetime
                from engine.config import TR_TZ

                dt = datetime.strptime(str(last)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TR_TZ)
                age = time.time() - dt.timestamp()
                if age < LAB_AUTO_INTERVAL_SEC:
                    return
            except Exception:
                pass
        if pipe.get("status") == "running":
            return

    result = run_lab_pipeline(log=pf.log, force=force)
    pf.lab_state = load_lab_state()
    pf._ensure_lab_ledgers()
    pf.save(sync_github=True)
    if result.get("promoted") or result.get("generated") or result.get("researched"):
        pf.log(f"Lab pipeline tamam: {result}")
