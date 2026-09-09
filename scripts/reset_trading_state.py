"""state.json: acik pozisyon + islem gecmisi sifirlama."""
from __future__ import annotations

import json
import sys
import urllib.request

from engine.config import GITHUB_BRANCH, GITHUB_REPO, KASA_START_USD, LEDGER_NAMES, STATE_FILE
from engine.github_sync import pull_json, push_json
from engine.portfolio import now_tr


def _fetch_raw_state() -> dict | None:
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/state.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return pull_json()


def reset_state(raw: dict | None) -> dict:
    base = dict(raw or {})
    ledgers = {k: KASA_START_USD for k in LEDGER_NAMES}
    for c in base.get("lab_candidates") or []:
        ledger = c.get("ledger")
        if ledger:
            ledgers[ledger] = KASA_START_USD
    balance = sum(ledgers.values())
    logs = list(base.get("engine_logs") or [])[-20:]
    logs.append(f"[{now_tr('%H:%M:%S')}] Islem gecmisi ve acik pozisyonlar sifirlandi (manual reset)")
    return {
        **base,
        "ledgers": ledgers,
        "balance": balance,
        "equity": balance,
        "closed_pnl_total": 0.0,
        "active_positions": {},
        "pending_orders": [],
        "history": [],
        "equity_curve": [],
        "engine_logs": logs[-100:],
        "updated_at": now_tr(),
    }


def main() -> int:
    raw = _fetch_raw_state()
    before_pos = len((raw or {}).get("active_positions") or {})
    before_hist = len((raw or {}).get("history") or {})
    clean = reset_state(raw)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
        f.write("\n")

    pushed = push_json(clean, message="Reset trading state: clear open positions and history")
    print(
        f"Sifirlandi: acik {before_pos}->0, kapanan {before_hist}->0, "
        f"equity={clean.get('equity')} github_push={'ok' if pushed else 'atlandi (token yok)'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
