#!/usr/bin/env bash
# VPS Web konsol — simule pozisyonlari sil, tarama modu icin 0 goster
set -euo pipefail
STATE="/opt/krpito/live_state.json"
python3 << 'PY'
import json
from pathlib import Path
p = Path("/opt/krpito/live_state.json")
if not p.exists():
    print("live_state.json yok")
    raise SystemExit(0)
d = json.loads(p.read_text(encoding="utf-8"))
n = len(d.get("active_positions") or {})
d["active_positions"] = {}
d["pending_orders"] = []
d["ledgers"] = {"Kasa_Canli": float(d.get("ledgers", {}).get("Kasa_Canli") or 100)}
p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Silindi: {n} simule pozisyon")
PY
systemctl restart krpito-live
echo "krpito-live yeniden baslatildi"
