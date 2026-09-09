"""Render motor JSON -> state.json + lab_state.json (GitHub Actions)."""
from __future__ import annotations

import json
import os
import sys
import urllib.request

ENGINE_URL = os.environ.get("ENGINE_URL", "https://mobil-tarama-kripto.onrender.com")


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "KrpitoStateSync/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def _load_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from engine.state_merge import merge_history

    snap = fetch(ENGINE_URL.rstrip("/"))
    pos = len(snap.get("active_positions") or {})
    hist = len(snap.get("history") or [])
    print(f"Render: acik={pos} kapanan={hist} equity={snap.get('equity')}")

    existing = _load_json("state.json")
    prev_hist = len(existing.get("history") or [])
    merged_hist = merge_history(existing.get("history"), snap.get("history"))
    snap["history"] = merged_hist
    snap["history_count"] = len(merged_hist)
    if merged_hist:
        snap["closed_pnl_total"] = sum(float(h.get("pnl") or 0) for h in merged_hist)
    if len(merged_hist) > hist:
        print(f"Islem gecmisi birlestirildi: github {prev_hist} + render {hist} -> {len(merged_hist)}")

    with open("state.json", "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
        f.write("\n")

    try:
        lab = fetch(ENGINE_URL.rstrip("/") + "/export/lab_state")
        with open("lab_state.json", "w", encoding="utf-8") as f:
            json.dump(lab, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"lab_state: recipes={len(lab.get('recipes') or [])} candidates={len(lab.get('candidates') or [])}")
    except Exception as e:
        print(f"lab_state atlandi (henuz deploy olmamis olabilir): {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
