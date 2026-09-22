"""Streamlit (GitHub state.json / Render paper) vs Hostinger live scan signal comparison."""
from __future__ import annotations

import json
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime

HOSTINGER_URL = "http://76.13.150.125:10001"
STREAMLIT_URL = "https://mobil-tarama-kripto.onrender.com"
GITHUB_STATE_URL = (
    "https://raw.githubusercontent.com/cumhursak53-del/Mobil-Tarama-Kripto/main/state.json"
)
HACIM_EVRE_PREFIXES = ("Evre_", "Hacim_")


def is_hacim_evre(rec: dict) -> bool:
    tags = rec.get("strategies") or []
    return any(any(p in str(t) for p in HACIM_EVRE_PREFIXES) for t in tags)


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "krpito-compare/1"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode())


def clean_sig(sig_log: dict | None) -> dict:
    return {k: v for k, v in (sig_log or {}).items() if not str(k).startswith("_")}


def parse_ts(s: str | None) -> datetime | None:
    if not s or s == "-":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def strat_stats(d: dict) -> tuple[Counter, dict[str, set[str]]]:
    c: Counter = Counter()
    sym_by_strat: dict[str, set[str]] = defaultdict(set)
    for sym, rec in d.items():
        for st in rec.get("strategies") or []:
            c[st] += 1
            sym_by_strat[st].add(sym)
    return c, sym_by_strat


def time_range(d: dict) -> tuple[datetime | None, datetime | None]:
    firsts, lasts = [], []
    for v in d.values():
        t1 = parse_ts(v.get("first_time"))
        t2 = parse_ts(v.get("last_time"))
        if t1:
            firsts.append(t1)
        if t2:
            lasts.append(t2)
    if not firsts:
        return None, None
    return min(firsts), max(lasts)


def pct(n: int, d: int) -> str:
    if not d:
        return "0%"
    return f"{100 * n / d:.1f}%"


def main() -> None:
    host = fetch(HOSTINGER_URL)
    stream = fetch(STREAMLIT_URL)

    hs = clean_sig(host.get("signal_log"))
    ss = clean_sig(stream.get("signal_log"))
    hs_f = {k: v for k, v in hs.items() if is_hacim_evre(v)}
    ss_f = {k: v for k, v in ss.items() if is_hacim_evre(v)}

    h_counts = [int(v.get("count") or 0) for v in hs.values()]
    s_counts = [int(v.get("count") or 0) for v in ss.values()]
    hf_counts = [int(v.get("count") or 0) for v in hs_f.values()]
    sf_counts = [int(v.get("count") or 0) for v in ss_f.values()]

    both = set(hs) & set(ss)
    both_f = set(hs_f) & set(ss_f)
    only_h = set(hs_f) - set(ss_f)
    only_s = set(ss_f) - set(hs_f)

    same_side = diff_side = 0
    side_pairs: list[tuple] = []
    for sym in both_f:
        h_side = hs_f[sym].get("last_side", "")
        s_side = ss_f[sym].get("last_side", "")
        if not (h_side and s_side):
            continue
        if h_side == s_side:
            same_side += 1
        else:
            diff_side += 1
            side_pairs.append(
                (sym, h_side, s_side, hs_f[sym].get("count"), ss_f[sym].get("count"))
            )

    hc, _ = strat_stats(hs_f)
    sc, _ = strat_stats(ss)
    scf, _ = strat_stats(ss_f)

    hf0, hf1 = time_range(hs_f)
    sf0, sf1 = time_range(ss_f)

    print("=" * 60)
    print("STREAMLIT vs HOSTINGER — SINYAL KARSILASTIRMA")
    print("=" * 60)
    print()
    print("=== KAYNAKLAR ===")
    print(f"Hostinger : {HOSTINGER_URL}")
    print(f"  mod={host.get('trading_mode')} | live_exchange={host.get('live_exchange')}")
    print(f"  updated_at={host.get('updated_at')}")
    print(f"Streamlit : Render paper motor ({STREAMLIT_URL})")
    print(f"  son log: {(stream.get('engine_logs') or ['-'])[-1]}")
    try:
        gh = fetch(GITHUB_STATE_URL)
        gh_sig = clean_sig(gh.get("signal_log"))
        gh_last = max(
            (parse_ts(v.get("last_time")) for v in gh_sig.values()),
            default=None,
        )
        print(f"  GitHub state.json son sinyal: {gh_last} (senkron gecikmesi icin)")
    except Exception:
        pass
    print()

    print("=== HACIM + PIYASAEVRESI OZET ===")
    print(
        f"Hostinger H+E : {len(hs_f):4d} sembol | {sum(hf_counts):6d} tetik | "
        f"ort {sum(hf_counts) / max(len(hs_f), 1):.1f}/sembol"
    )
    print(
        f"Streamlit tum : {len(ss):4d} sembol | {sum(s_counts):6d} tetik | "
        f"ort {sum(s_counts) / max(len(ss), 1):.1f}/sembol"
    )
    print(
        f"Streamlit H+E : {len(ss_f):4d} sembol | {sum(sf_counts):6d} tetik | "
        f"ort {sum(sf_counts) / max(len(ss_f), 1):.1f}/sembol"
    )
    print(
        f"Hostinger tum : {len(hs):4d} sembol | {sum(h_counts):6d} tetik "
        f"(scan-only tekrar dahil)"
    )
    print()

    print("=== ZAMAN ARALIGI (signal_log) ===")
    print(f"Hostinger : {hf0}  ->  {hf1}")
    print(f"Streamlit : {sf0}  ->  {sf1}")
    print()

    print("=== SEMBOL KESISIMI ===")
    print(f"Ortak H+E sembol            : {len(both_f):4d}  ({pct(len(both_f), len(hs_f))} of Hostinger H+E)")
    print(f"Sadece Hostinger H+E        : {len(only_h):4d}")
    print(f"Sadece Streamlit H+E        : {len(only_s):4d}")
    print(f"(Tum stratejiler ortak)     : {len(both):4d}")
    aligned = same_side + diff_side
    print(
        f"Son yon uyumu (ortak {aligned} sembol): "
        f"{same_side} ayni ({pct(same_side, aligned)}), {diff_side} farkli"
    )
    print()

    print("=== STRATEJI (unique sembol sayisi) ===")
    print("Hostinger    :", dict(hc))
    print("Streamlit    :", dict(sc))
    print("Streamlit H+E:", dict(scf))
    print()

    print("=== HOSTINGER H+E TEKRAR DAGILIMI (count/sembol) ===")
    if hf_counts:
        hs_sorted = sorted(hf_counts)
        for q in (50, 75, 90, 95, 99):
            idx = min(len(hs_sorted) - 1, int(len(hs_sorted) * q / 100))
            print(f"  p{q:2d}: {hs_sorted[idx]:4d}")
        print(f"  max: {max(hf_counts)}")
        top_h = sorted(hs_f.items(), key=lambda x: int(x[1].get("count") or 0), reverse=True)[:10]
        print("  En cok tekrar:")
        for sym, rec in top_h:
            st = (rec.get("strategies") or ["?"])[0]
            print(
                f"    {sym:16s} count={rec.get('count'):4d} "
                f"{rec.get('last_side'):4s} {st}"
            )
    print()

    print("=== YON CATISMASI (ortak semboller, top 15) ===")
    if not side_pairs:
        print("  Yok")
    else:
        for row in sorted(side_pairs, key=lambda x: (x[3] or 0) + (x[4] or 0), reverse=True)[:15]:
            print(f"  {row[0]:16s} Hostinger={row[1]}({row[3]})  Streamlit={row[2]}({row[4]})")
    print()

    print("=== ORTAK H+E SEMBOLLERDE STRATEJI KESISIMI ===")
    def tag_set(rec: dict) -> set[str]:
        return {str(t) for t in (rec.get("strategies") or [])}

    strat_overlap = sum(
        1 for sym in both_f if tag_set(hs[sym]) & tag_set(ss_f[sym])
    )
    print(f"  {strat_overlap} / {len(both_f)} sembolde ayni strateji de var")
    print()

    ap = stream.get("active_positions") or {}
    he_pos = {
        k: v
        for k, v in ap.items()
        if str(v.get("ledger") or "") in ("Kasa_Hacim", "Kasa_PiyasaEvresi")
    }
    print("=== STREAMLIT ACIK POZISYON ===")
    print(f"  Toplam acik: {len(ap)} | Hacim/Evre acik: {len(he_pos)}")
    print(f"  Ledger: {dict(Counter(v.get('ledger') for v in ap.values()))}")
    print()

    # Side breakdown
    h_buy = sum(1 for v in hs_f.values() if v.get("last_side") == "BUY")
    h_sell = sum(1 for v in hs_f.values() if v.get("last_side") == "SELL")
    s_buy = sum(1 for v in ss_f.values() if v.get("last_side") == "BUY")
    s_sell = sum(1 for v in ss_f.values() if v.get("last_side") == "SELL")
    print("=== SON YON DAGILIMI (H+E) ===")
    print(f"  Hostinger : BUY {h_buy} | SELL {h_sell}")
    print(f"  Streamlit : BUY {s_buy} | SELL {s_sell}")
    print()

    print("=== SONUC OZETI ===")
    ratio = sum(hf_counts) / max(sum(sf_counts), 1)
    print(f"  1) Hostinger H+E ~{ratio:.0f}x daha fazla tetik (scan-only, live entry tekrar log)")
    print(f"  2) Evren: Hostinger H+E {len(hs_f)} vs Streamlit H+E {len(ss_f)} sembol")
    print(f"  3) Ortak {len(both_f)} sembolde son yon uyumu: {pct(same_side, aligned)}")
    if diff_side:
        print(f"  4) {diff_side} ortak sembolde son yon farkli")
    print(f"  5) Streamlit H+E sinyali var ama acik H+E pozisyon: {len(he_pos)} (ayri kasalar)")
    print()


if __name__ == "__main__":
    main()
