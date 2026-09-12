from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from engine.config import CREW_AUTO, CREW_INTERVAL_SEC, GEMINI_API_KEY
from engine.crew.pipeline import run_daily_crew
from engine.crew.sync import load_crew_state, sync_crew_state
from engine.crew.state import now_tr
from engine.gemini_client import gemini_usable

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
            "last_message": "",
            "last_passed": 0,
            "last_tested": 0,
        },
    )


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


def run_crew_pipeline(*, log=None, force: bool = False) -> dict:
    global _running
    if not _lock.acquire(blocking=False):
        return {"skipped": "busy"}
    _running = True
    state = load_crew_state()
    pipe = _pipeline(state)
    pipe["status"] = "running"
    pipe["last_message"] = "Crew calisiyor..."
    try:
        sync_crew_state(state)
    except Exception:
        pass

    def _log(msg: str) -> None:
        line = f"Crew: {msg}"
        if log:
            log(line)
        else:
            print(f"[{now_tr('%H:%M:%S')}] {line}", flush=True)

    try:
        if not GEMINI_API_KEY:
            _log("atlandi — GEMINI_API_KEY yok")
            pipe["status"] = "error"
            pipe["last_message"] = "GEMINI_API_KEY yok"
            pipe["last_run_at"] = now_tr()
            state = load_crew_state()
            _pipeline(state).update(pipe)
            sync_crew_state(state)
            return {"error": "no_gemini_key"}

        if not gemini_usable() and not force:
            _log("atlandi — Gemini kota beklemede")
            return {"skipped": "gemini_quota"}

        _log("gunluk strateji uretimi basladi (%20 hedef)")
        out = run_daily_crew(send_email=False, dry_run=False, log=_log)
        summary = out.get("summary") or {}
        state = load_crew_state()
        pipe = _pipeline(state)
        pipe["status"] = "ok"
        pipe["last_run_at"] = now_tr()
        pipe["last_passed"] = int(summary.get("recipes_passed") or 0)
        pipe["last_tested"] = int(summary.get("recipes_tested") or 0)
        pipe["last_message"] = (
            f"Uretilen {summary.get('recipes_generated', 0)} | "
            f"Test {pipe['last_tested']} | Gecen %{summary.get('recipes_passed', 0)} aday"
        )
        sync_crew_state(state)
        _log(f"tamam — {pipe['last_message']}")
        return {"summary": summary, "errors": out.get("errors") or []}
    except Exception as e:
        state = load_crew_state()
        pipe = _pipeline(state)
        pipe["status"] = "error"
        pipe["last_message"] = str(e)[:200]
        pipe["last_run_at"] = now_tr()
        sync_crew_state(state)
        _log(f"hata — {e}")
        return {"error": str(e)}
    finally:
        _running = False
        _lock.release()


def maybe_run_crew(pf: "Portfolio", force: bool = False) -> None:
    if not CREW_AUTO:
        return
    state = pf.crew_state or load_crew_state()
    pipe = state.get("pipeline") or {}
    if not force:
        age = _age_sec(pipe.get("last_run_at") or "")
        if age is not None and age < CREW_INTERVAL_SEC:
            return
        if pipe.get("status") == "running" and _running:
            return

    def _bg():
        run_crew_pipeline(log=pf.log, force=force)
        pf.crew_state = load_crew_state()

    threading.Thread(target=_bg, daemon=True).start()
