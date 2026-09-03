from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime

from engine.config import (
    GITHUB_BRANCH,
    KASA_START_USD,
    LAB_FREEZE,
    LAB_LEDGER_PREFIX,
    LAB_MAX_CANDIDATES,
    LAB_STATE_FILE,
    TR_TZ,
)
from engine.github_sync import pull_json, push_json

LAB_SCHEMA_VERSION = 1


def now_tr(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now(TR_TZ).strftime(fmt)


@dataclass
class LabMetrics:
    n: int = 0
    wins: int = 0
    pnl: float = 0.0

    @property
    def wr(self) -> float:
        return self.wins / self.n if self.n else 0.0

    def to_dict(self) -> dict:
        return {"n": self.n, "wins": self.wins, "pnl": self.pnl, "wr": self.wr}


@dataclass
class LabCandidate:
    recipe_id: str
    ledger: str
    status: str = "paper"
    paper_started_at: str = ""
    metrics: dict = field(default_factory=dict)
    backtest: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def empty_lab_state() -> dict:
    return {
        "schema_version": LAB_SCHEMA_VERSION,
        "recipes": [],
        "backtests": [],
        "candidates": [],
        "updated_at": now_tr(),
    }


def load_lab_state_local() -> dict:
    if not os.path.exists(LAB_STATE_FILE):
        return empty_lab_state()
    try:
        with open(LAB_STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return empty_lab_state()


def save_lab_state_local(state: dict) -> None:
    state["updated_at"] = now_tr()
    with open(LAB_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_lab_state() -> dict:
    local = load_lab_state_local()
    remote = pull_json(LAB_STATE_FILE)
    if remote and not local.get("candidates") and not local.get("recipes"):
        local = remote
    elif remote:
        lt = str(local.get("updated_at") or "")
        rt = str(remote.get("updated_at") or "")
        if rt >= lt:
            local = remote
    save_lab_state_local(local)
    return local


def sync_lab_state(state: dict) -> None:
    save_lab_state_local(state)
    push_json(state, LAB_STATE_FILE, message=f"Lab state update [{GITHUB_BRANCH}]")


def recipe_by_id(state: dict, recipe_id: str) -> dict | None:
    for r in state.get("recipes") or []:
        if r.get("id") == recipe_id:
            return r
    return None


def next_lab_ledger(state: dict) -> str | None:
    active = [c for c in state.get("candidates") or [] if c.get("status") == "paper"]
    if len(active) >= LAB_MAX_CANDIDATES:
        return None
    used = {c.get("ledger") for c in state.get("candidates") or []}
    n = 1
    while n < 100:
        name = f"{LAB_LEDGER_PREFIX}{n:03d}"
        if name not in used:
            return name
        n += 1
    return None


def promote_recipe(state: dict, recipe: dict, backtest: dict) -> LabCandidate | None:
    if LAB_FREEZE:
        return None
    rid = recipe.get("id")
    if not rid:
        return None
    for c in state.get("candidates") or []:
        if c.get("recipe_id") == rid and c.get("status") == "paper":
            return LabCandidate(**c)
    ledger = next_lab_ledger(state)
    if not ledger:
        return None
    recipes = state.setdefault("recipes", [])
    if not any(r.get("id") == rid for r in recipes):
        recipes.append(deepcopy(recipe))
    cand = LabCandidate(
        recipe_id=rid,
        ledger=ledger,
        status="paper",
        paper_started_at=now_tr(),
        metrics=LabMetrics().to_dict(),
        backtest=backtest,
    )
    state.setdefault("candidates", []).append(cand.to_dict())
    return cand


def record_lab_trade(state: dict, ledger: str, pnl: float) -> None:
    for c in state.get("candidates") or []:
        if c.get("ledger") != ledger or c.get("status") != "paper":
            continue
        m = c.setdefault("metrics", {"n": 0, "wins": 0, "pnl": 0.0, "wr": 0.0})
        m["n"] = int(m.get("n") or 0) + 1
        if pnl > 0:
            m["wins"] = int(m.get("wins") or 0) + 1
        m["pnl"] = float(m.get("pnl") or 0) + float(pnl)
        m["wr"] = m["wins"] / m["n"] if m["n"] else 0.0
        break


def reject_candidate(state: dict, ledger: str, reason: str = "") -> None:
    for c in state.get("candidates") or []:
        if c.get("ledger") == ledger:
            c["status"] = "rejected"
            c["rejected_at"] = now_tr()
            if reason:
                c["reject_reason"] = reason


def evaluate_lab_candidates(state: dict) -> list[str]:
    rejected = []
    for c in state.get("candidates") or []:
        if c.get("status") != "paper":
            continue
        m = c.get("metrics") or {}
        n = int(m.get("n") or 0)
        if n < 15:
            continue
        wr = float(m.get("wr") or 0)
        pnl = float(m.get("pnl") or 0)
        if wr < 0.35 or pnl < 0:
            reject_candidate(state, c.get("ledger", ""), "paper_underperform")
            rejected.append(c.get("ledger", ""))
    return rejected


def new_recipe_id() -> str:
    return str(uuid.uuid4())[:8]
