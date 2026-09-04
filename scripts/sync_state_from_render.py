"""Render motor JSON -> state.json + lab_state.json (GitHub Actions)."""
from __future__ import annotations

import json
import sys
import urllib.request

ENGINE_URL = "https://mobil-tarama-kripto.onrender.com"


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "KrpitoStateSync/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def main() -> int:
    snap = fetch(ENGINE_URL.rstrip("/"))
    pos = len(snap.get("active_positions") or {})
    hist = len(snap.get("history") or [])
    print(f"Render: acik={pos} kapanan={hist} equity={snap.get('equity')}")

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
