from __future__ import annotations

import json
import os

from engine.config import GITHUB_BRANCH, GITHUB_TOKEN
from engine.crew.config import CREW_STATE_FILE
from engine.crew.state import default_state, now_tr
from engine.github_sync import pull_json, push_json


def load_crew_state_local() -> dict:
    if not os.path.exists(CREW_STATE_FILE):
        return default_state()
    try:
        with open(CREW_STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return default_state()


def save_crew_state_local(state: dict) -> None:
    state["updated_at"] = now_tr()
    with open(CREW_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_crew_state() -> dict:
    local = load_crew_state_local()
    remote = pull_json(CREW_STATE_FILE)
    if remote and not local.get("daily_runs") and not local.get("recipes"):
        local = remote
    elif remote:
        lt = str(local.get("updated_at") or "")
        rt = str(remote.get("updated_at") or "")
        if rt >= lt:
            local = remote
    save_crew_state_local(local)
    return local


def sync_crew_state(state: dict) -> None:
    save_crew_state_local(state)
    push_json(state, CREW_STATE_FILE, message=f"Crew state update [{GITHUB_BRANCH}]")
