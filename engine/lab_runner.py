from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Optional

from engine.config import (
    GEMINI_API_KEY,
    GEMINI_SKIP_PIPELINE_TEST,
    LAB_AUTO,
    LAB_AUTO_INTERVAL_SEC,
    LAB_BACKTEST_BATCH,
    LAB_BACKTEST_UNIVERSE,
    LAB_COMBINATOR_ON_IDLE,
    LAB_FREEZE,
    LAB_GENERATE_LIMIT,
    LAB_MAX_CANDIDATES,
    LAB_MAX_RECIPES,
    LAB_MIN_RECIPES,
    LAB_QUICK_SCREEN_SYMBOL,
    RESEARCH_ENABLED,
    RESEARCH_INTERVAL_SEC,
    RESEARCH_SEPARATE,
)
from engine.data import fetch_all_timeframes, fetch_dominance, fetch_symbols
from engine.lab_backtest import quick_screen_recipe
from engine.lab_state import load_lab_state, now_tr, promote_recipe, sync_lab_state
from engine.research_queue import (
    ensure_source_metrics,
    record_backtest_outcome,
    record_paper_promotion,
    record_recipes_added,
)
from engine.research_runner import run_research
from engine.strategy_generator import generate_recipes

if TYPE_CHECKING:
    from engine.portfolio import Portfolio

_lock = threading.Lock()
_research_lock = threading.Lock()
_running = False
_research_running = False


def _pipeline(state: dict) -> dict:
    return state.setdefault(
        "pipeline",
        {
            "status": "idle",
            "last_run_at": "",
            "last_research_at": "",
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
        if limit > 0 and len(out) >= limit:
            break
    return out


def _paper_slots_free(state: dict) -> int:
    if LAB_MAX_CANDIDATES <= 0:
        return 10**9
    active = len([c for c in state.get("candidates") or [] if c.get("status") == "paper"])
    return max(0, LAB_MAX_CANDIDATES - active)


def _run_research_phase(state: dict, *, log=None, force: bool = False) -> int:
    researched = 0
    ensure_source_metrics(state)
    research_meta = state.setdefault("research", {})
    research_meta["gemini_configured"] = bool(GEMINI_API_KEY)
    research_meta["research_enabled"] = RESEARCH_ENABLED

    if not RESEARCH_ENABLED:
        return 0
    if not GEMINI_API_KEY:
        if log:
            log("Arastirma atlandi: GEMINI_API_KEY worker env'de tanimli degil")
        return 0

    from engine.gemini_client import gemini_usable, test_gemini_connection

    if gemini_usable() and not GEMINI_SKIP_PIPELINE_TEST and force:
        test_gemini_connection(log=log)
    if not gemini_usable():
        if log:
            log("Arastirma atlandi: Gemini kota beklemede")
        return 0

    new_research = run_research(state, log=log)
    if new_research:
        state.setdefault("recipes", []).extend(new_research)
        record_recipes_added(state, new_research)
        researched = len(new_research)
        if log:
            log(f"Arastirma: {researched} yeni tarif (YouTube/haber/web/Gemini)")
    return researched


def _maybe_combinator(state: dict, *, log=None, force: bool = False) -> int:
    recipes = state.get("recipes") or []
    if len(recipes) >= LAB_MAX_RECIPES:
        return 0
    pending = len(_pending_recipes(state, 1))
    slots = _paper_slots_free(state)
    need_recipes = len(recipes) < LAB_MIN_RECIPES
    if LAB_COMBINATOR_ON_IDLE and pending == 0 and slots > 0:
        need_recipes = True
    if force and pending == 0 and slots > 0:
        need_recipes = True
    if not need_recipes:
        return 0
    batch = min(LAB_GENERATE_LIMIT, max(8, slots * 3))
    new_recipes = generate_recipes(limit=batch)
    state.setdefault("recipes", []).extend(new_recipes)
    record_recipes_added(state, new_recipes)
    if log:
        log(f"Lab: {len(new_recipes)} yeni tarif uretildi (toplam {len(state['recipes'])})")
    return len(new_recipes)


def _run_backtest_phase(state: dict, *, log=None) -> tuple[int, int]:
    pending = _pending_recipes(state, LAB_BACKTEST_BATCH)
    backtested = 0
    promoted = 0
    if not pending:
        return backtested, promoted

    symbols = fetch_symbols(LAB_BACKTEST_UNIVERSE)[:LAB_BACKTEST_UNIVERSE]
    dominance = fetch_dominance()
    symbol_frames: dict[str, dict] = {}
    for sym in symbols:
        try:
            symbol_frames[sym] = fetch_all_timeframes(sym)
            time.sleep(0.1)
        except Exception as e:
            if log:
                log(f"Lab veri hatasi {sym}: {e}")

    if not symbol_frames:
        return backtested, promoted

    screen_sym = LAB_QUICK_SCREEN_SYMBOL if LAB_QUICK_SCREEN_SYMBOL in symbol_frames else next(iter(symbol_frames))
    screen_frames = symbol_frames[screen_sym]

    qualified: list[dict] = []
    for recipe in pending:
        qs = quick_screen_recipe(recipe, screen_sym, screen_frames, dominance)
        metrics = qs.get("metrics") or {}
        if qs.get("passed"):
            qualified.append(recipe)
            continue
        record_backtest_outcome(state, recipe, metrics, quick_fail=True)
        state.setdefault("backtests", []).append({
            "recipe_id": recipe.get("id"),
            "metrics": {**metrics, "passed": False, "stage": "quick_screen"},
            "symbols": [screen_sym],
            "run_at": now_tr(),
        })
        backtested += 1
        if log:
            log(f"Lab hizli eleme FAIL {recipe.get('id')} ({screen_sym}) PF={metrics.get('profit_factor')}")

    if not qualified:
        return backtested, promoted

    from engine.walk_forward import walk_forward_recipe_batch

    rows = walk_forward_recipe_batch(qualified, symbol_frames, dominance)
    for row in rows:
        recipe = row["recipe"]
        m = row["metrics"]
        record_backtest_outcome(state, recipe, m, quick_fail=False)
        state.setdefault("backtests", []).append({
            "recipe_id": recipe.get("id"),
            "metrics": m,
            "symbols": list(symbol_frames.keys()),
            "run_at": now_tr(),
            "stage": "walk_forward",
        })
        backtested += 1
        if m.get("passed") and _paper_slots_free(state) > 0:
            cand = promote_recipe(state, recipe, m)
            if cand:
                record_paper_promotion(state, recipe)
                promoted += 1
                if log:
                    log(f"Lab: aday secildi {cand.ledger} (tarif {cand.recipe_id})")
    if log:
        log(f"Lab backtest: {backtested} tarif, {promoted} aday paper'a alindi")
    return backtested, promoted


def run_research_pipeline(*, log=None, force: bool = False) -> dict:
    """Sadece arastirma — backtest yapmaz."""
    global _research_running
    if LAB_FREEZE or not LAB_AUTO or not RESEARCH_ENABLED:
        return {"skipped": True, "reason": "research_disabled"}

    if not _research_lock.acquire(blocking=False):
        return {"skipped": True, "reason": "research_already_running"}

    _research_running = True
    try:
        state = load_lab_state()
        pipe = _pipeline(state)
        pipe["status"] = "running"
        pipe["last_message"] = "Arastirma calisiyor..."
        sync_lab_state(state)

        researched = _run_research_phase(state, log=log, force=force)
        generated = _maybe_combinator(state, log=log, force=force) if researched == 0 else 0

        backtested, promoted = 0, 0
        if researched or generated:
            backtested, promoted = _run_backtest_phase(state, log=log)

        pipe["status"] = "ok"
        pipe["last_research_at"] = now_tr()
        pipe["last_researched"] = researched
        if generated:
            pipe["last_generate_at"] = now_tr()
            pipe["last_generated"] = generated
        if backtested:
            pipe["last_backtest_at"] = now_tr()
            pipe["last_backtested"] = backtested
            pipe["last_promoted"] = promoted
        pipe["last_message"] = (
            f"Arastirma {researched}, kombinator {generated}, backtest {backtested}, aday {promoted}"
        )
        sync_lab_state(state)
        return {
            "researched": researched,
            "generated": generated,
            "backtested": backtested,
            "promoted": promoted,
            "recipe_total": len(state.get("recipes") or []),
        }
    except Exception as e:
        try:
            state = load_lab_state()
            pipe = _pipeline(state)
            pipe["status"] = "error"
            pipe["last_message"] = str(e)[:200]
            pipe["last_research_at"] = now_tr()
            sync_lab_state(state)
        except Exception:
            pass
        if log:
            log(f"Arastirma hatasi: {e}")
        return {"error": str(e)}
    finally:
        _research_running = False
        _research_lock.release()


def run_lab_pipeline(*, log=None, force: bool = False) -> dict:
    """Backtest + aday sec (+ ayri mod kapaliysa arastirma)."""
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
        ensure_source_metrics(state)
        sync_lab_state(state)

        researched = 0
        generated = 0
        if not RESEARCH_SEPARATE:
            researched = _run_research_phase(state, log=log, force=force)
            pipe["last_researched"] = researched

        generated = _maybe_combinator(state, log=log, force=force)
        if generated:
            pipe["last_generate_at"] = now_tr()
            pipe["last_generated"] = generated

        backtested, promoted = _run_backtest_phase(state, log=log)
        if backtested:
            pipe["last_backtest_at"] = now_tr()
            pipe["last_backtested"] = backtested
            pipe["last_promoted"] = promoted

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


def _age_sec(timestamp: str) -> float | None:
    if not timestamp:
        return None
    try:
        from datetime import datetime
        from engine.config import TR_TZ

        dt = datetime.strptime(str(timestamp)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TR_TZ)
        return time.time() - dt.timestamp()
    except Exception:
        return None


def maybe_run_research(pf: "Portfolio", force: bool = False) -> None:
    if LAB_FREEZE or not LAB_AUTO or not RESEARCH_ENABLED or not RESEARCH_SEPARATE:
        return
    state = pf.lab_state or load_lab_state()
    pipe = state.get("pipeline") or {}
    if not force:
        age = _age_sec(pipe.get("last_research_at") or "")
        if age is not None and age < RESEARCH_INTERVAL_SEC:
            return
        if pipe.get("status") == "running" and _research_running:
            return

    result = run_research_pipeline(log=pf.log, force=force)
    pf.lab_state = load_lab_state()
    pf._ensure_lab_ledgers()
    pf.save(sync_github=True)
    if result.get("researched") or result.get("generated") or result.get("backtested"):
        pf.log(f"Arastirma tamam: {result}")


def maybe_run_lab_pipeline(pf: "Portfolio", force: bool = False) -> None:
    if LAB_FREEZE or not LAB_AUTO:
        return
    state = pf.lab_state or load_lab_state()
    pipe = state.get("pipeline") or {}
    if not force:
        age = _age_sec(pipe.get("last_run_at") or "")
        if age is not None and age < LAB_AUTO_INTERVAL_SEC:
            return
        if pipe.get("status") == "running" and _running:
            return

    result = run_lab_pipeline(log=pf.log, force=force)
    pf.lab_state = load_lab_state()
    pf._ensure_lab_ledgers()
    pf.save(sync_github=True)
    if result.get("promoted") or result.get("generated") or result.get("backtested"):
        pf.log(f"Lab pipeline tamam: {result}")
