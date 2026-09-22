"""Hostinger signal_log + recent engine_logs: same-coin flip analysis."""
from __future__ import annotations

import json
import re
import urllib.request
from collections import defaultdict

HOSTINGER_URL = "http://76.13.150.125:10001"


def fetch() -> dict:
    req = urllib.request.Request(HOSTINGER_URL, headers={"User-Agent": "krpito-check/1"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    data = fetch()
    logs = data.get("engine_logs") or []
    sig_log = {
        k: v for k, v in (data.get("signal_log") or {}).items() if not str(k).startswith("_")
    }

    pat = re.compile(r"sinyal (\S+) \| ([^|]+) \| (BUY|SELL) \| skor ([\d.]+)")
    events: list[tuple[str, str, str, str, float]] = []
    for line in logs:
        m = pat.search(line)
        if m:
            events.append(
                (line[:11], m.group(1), m.group(2).strip(), m.group(3), float(m.group(4)))
            )

    print("=== HOSTINGER SINYAL ANALIZI ===")
    print(f"updated_at: {data.get('updated_at')}")
    print(f"signal_log sembol: {len(sig_log)}")
    print(f"engine_logs: {len(logs)} satir | sinyal satiri (son buffer): {len(events)}")
    print()

    flips: list[tuple] = []
    for i, ev in enumerate(events):
        if i == 0:
            continue
        prev = events[i - 1]
        if prev[1] == ev[1] and (prev[3] != ev[3] or prev[2] != ev[2]):
            flips.append((prev, ev))

    print("=== SON ~100 LOG: ARDISIK FARKLI SINYAL (ayni coin) ===")
    print(f"Adet: {len(flips)}")
    if not flips:
        print("  Yok — son log penceresinde arka arkaya yon/strateji degisimi gorulmedi.")
    else:
        for a, b in flips[:25]:
            print(
                f"  {a[1]:16s} | {a[3]} -> {b[3]} | "
                f"{a[2][:35]} -> {b[2][:35]}"
            )
    print()

    multi_strat = [(s, v) for s, v in sig_log.items() if len(v.get("strategies") or []) > 1]
    print("=== OTURUM BOYU: AYNI COINDE BIRDEN FAZLA STRATEJI ===")
    print(f"Sembol: {len(multi_strat)}")
    for sym, v in sorted(multi_strat, key=lambda x: int(x[1].get("count") or 0), reverse=True)[:20]:
        cnt = int(v.get("count") or 0)
        print(f"  {sym:16s} count={cnt:4d} last={v.get('last_side')} | {v.get('strategies')}")
    print()

    # Infer side flips: can't know full history, but show symbols with both hacim buy/sell tags
    hacim_both = []
    for sym, v in sig_log.items():
        tags = [str(t) for t in (v.get("strategies") or [])]
        has_buy = any("Pozitif" in t or "Long" in t or "Spring" in t for t in tags)
        has_sell = any("Negatif" in t or "Short" in t or "Upthrust" in t for t in tags)
        if has_buy and has_sell:
            hacim_both.append((sym, v))
    print("=== OTURUM: HEM LONG HEM SHORT ETIKETI OLAN COINLER ===")
    print(f"Sembol: {len(hacim_both)}")
    for sym, v in hacim_both[:15]:
        print(f"  {sym:16s} last={v.get('last_side')} count={v.get('count')} | {v.get('strategies')}")
    print()

    high = sorted(sig_log.items(), key=lambda x: int(x[1].get("count") or 0), reverse=True)[:12]
    print("=== EN COK TEKRAR (genelde ayni yon/strateji) ===")
    for sym, v in high:
        cnt = int(v.get("count") or 0)
        print(
            f"  {sym:16s} count={cnt:4d} last={v.get('last_side')} | "
            f"{(v.get('strategies') or ['?'])[0]}"
        )
    print()
    print("NOT: engine_logs yalnizca son 100 satir tutulur; signal_log count birikimlidir.")


if __name__ == "__main__":
    main()
