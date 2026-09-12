from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime

from engine.config import TR_TZ
from engine.crew.config import CREW_STATE_FILE


def now_tr(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now(TR_TZ).strftime(fmt)


def default_state() -> dict:
    return {
        "schema_version": 1,
        "updated_at": "",
        "recipes": [],
        "backtests": [],
        "daily_runs": [],
        "research": {
            "processed_videos": [],
            "processed_web_queries": [],
            "last_youtube_at": "",
            "last_news_at": "",
            "last_web_at": "",
        },
    }


def load_state(path: str | None = None) -> dict:
    p = path or CREW_STATE_FILE
    if not os.path.exists(p):
        return default_state()
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return default_state()
        base = default_state()
        base.update(raw)
        base.setdefault("recipes", [])
        base.setdefault("backtests", [])
        base.setdefault("daily_runs", [])
        base.setdefault("research", default_state()["research"])
        return base
    except Exception:
        return default_state()


def save_state(state: dict, path: str | None = None, *, sync_github: bool = True) -> None:
    state = deepcopy(state)
    state["updated_at"] = now_tr()
    if sync_github:
        from engine.crew.sync import sync_crew_state

        sync_crew_state(state)
        return
    p = path or CREW_STATE_FILE
    with open(p, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def append_recipes(state: dict, recipes: list[dict]) -> int:
    existing = {r.get("id") for r in state.get("recipes") or []}
    added = 0
    for r in recipes:
        rid = r.get("id")
        if rid and rid not in existing:
            r = dict(r)
            r.setdefault("source", "crewai")
            state.setdefault("recipes", []).append(r)
            existing.add(rid)
            added += 1
    return added
