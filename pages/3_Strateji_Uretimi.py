"""Strateji uretim hatti — canli durum izleme sayfasi."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.config import LAB_LEDGER_PREFIX, LAB_MAX_CANDIDATES
from ui_common import (
    engine_status,
    load_lab_data,
    minutes_since_update,
    setup_page,
    source_caption,
)

data = setup_page("Strateji Uretimi", icon="⚙️")
lab_remote = load_lab_data(force_version=st.session_state.get("refresh_version", 0))

engine_data = data
lab_summary = engine_data.get("lab_summary") or {}
lab_candidates = engine_data.get("lab_candidates") or []
active = engine_data.get("active_positions") or {}
history = engine_data.get("history") or []
logs = engine_data.get("engine_logs") or []
ledgers = engine_data.get("ledgers") or {}

# GitHub lab_state daha taze ise onu kullan
remote_mins = minutes_since_update(lab_remote.get("updated_at"))
summary_mins = minutes_since_update(lab_summary.get("updated_at"))
if remote_mins is not None and (summary_mins is None or remote_mins <= summary_mins):
    lab_summary = {
        "updated_at": lab_remote.get("updated_at"),
        "recipe_count": len(lab_remote.get("recipes") or []),
        "backtest_count": len(lab_remote.get("backtests") or []),
        "paper_count": len([c for c in lab_remote.get("candidates") or [] if c.get("status") == "paper"]),
        "rejected_count": len([c for c in lab_remote.get("candidates") or [] if c.get("status") == "rejected"]),
        "recent_backtests": (lab_remote.get("backtests") or [])[-10:],
        "all_candidates": lab_remote.get("candidates") or [],
    }
    lab_candidates = [c for c in lab_remote.get("candidates") or [] if c.get("status") == "paper"]

st.title("Strateji uretimi — canli durum")
st.caption(source_caption(engine_data))
st.markdown(
    "Bu sayfa **tarif uretimi → backtest → paper aday kasa** hattinin calisip calismadigini gosterir. "
    "Sol menuden **Simdi yenile** ile guncelleyebilirsin."
)

motor_label, motor_level, motor_note = engine_status(engine_data)
lab_mins = minutes_since_update(lab_summary.get("updated_at"))
recipe_n = int(lab_summary.get("recipe_count") or 0)
bt_n = int(lab_summary.get("backtest_count") or 0)
paper_n = int(lab_summary.get("paper_count") or 0)
rejected_n = int(lab_summary.get("rejected_count") or 0)

lab_open = [p for p in active.values() if str(p.get("ledger_name", "")).startswith(LAB_LEDGER_PREFIX)]
lab_hist = [h for h in history if str(h.get("ledger", "")).startswith(LAB_LEDGER_PREFIX)]
lab_signals = [
    (sym, s) for sym, s in (engine_data.get("signal_log") or {}).items()
    if isinstance(s, dict) and str(s.get("last_ledger", "")).startswith(LAB_LEDGER_PREFIX)
]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Paper motoru", motor_label, motor_note)
c2.metric("Lab state", f"{recipe_n} tarif", f"Guncelleme: {lab_summary.get('updated_at') or '-'}")
c3.metric("Backtest kaydi", bt_n)
c4.metric("Paper aday", f"{paper_n}/{LAB_MAX_CANDIDATES}")
c5.metric("Lab acik islem", len(lab_open))

if motor_level == "ok":
    st.success("Motor canli veri gonderiyor.")
elif motor_level == "warn":
    st.warning("Motor yavas veya gecikmeli; birkaç dakika bekleyip yenile.")
else:
    st.error("Motor verisi gelmiyor. Render servisi uyuyor olabilir veya deploy bekliyor.")

st.subheader("Uretim hatti adimlari")

steps = [
    (
        "1. Tarif havuzu",
        recipe_n > 0,
        f"{recipe_n} tarif kayitli" if recipe_n else "Henuz tarif yok — Render shell: lab-generate",
    ),
    (
        "2. Backtest calisti",
        bt_n > 0,
        f"{bt_n} backtest kaydi" if bt_n else "Backtest yok — Render shell: lab-backtest",
    ),
    (
        "3. Paper aday secildi",
        paper_n > 0,
        f"{paper_n} aday kasada" if paper_n else "Gecen aday yok (PF/WR esigi veya slot dolu)",
    ),
    (
        "4. Lab islem acti",
        len(lab_open) > 0 or len(lab_hist) > 0,
        f"{len(lab_open)} acik, {len(lab_hist)} kapanmis lab islemi",
    ),
    (
        "5. Lab state GitHub sync",
        lab_mins is not None and lab_mins <= 30,
        f"Son lab_state: {lab_summary.get('updated_at') or 'yok'}",
    ),
]

for title, ok, detail in steps:
    icon = "✅" if ok else "⏳"
    if ok:
        st.markdown(f"**{icon} {title}** — {detail}")
    else:
        st.markdown(f"**{icon} {title}** — {detail}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Aday kasalar", "Backtest sonuclari", "Lab islemleri", "Reddedilenler", "Motor log"]
)

with tab1:
    if lab_candidates:
        rows = []
        for c in lab_candidates:
            m = c.get("metrics") or {}
            bt = c.get("backtest") or {}
            bal = float(ledgers.get(c.get("ledger", ""), 100))
            rows.append({
                "Kasa": c.get("ledger"),
                "Tarif ID": c.get("recipe_id"),
                "Durum": c.get("status", "paper"),
                "Paper baslangic": c.get("paper_started_at", "-"),
                "Kasa bakiye": f"${bal:.2f}",
                "Islem": m.get("n", 0),
                "WR": f"{100 * float(m.get('wr') or 0):.0f}%",
                "Paper PnL": f"${float(m.get('pnl') or 0):+.2f}",
                "BT islem": bt.get("n", "-"),
                "BT PF": bt.get("profit_factor", "-"),
                "BT gecti": "Evet" if bt.get("passed") else "Hayir",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(
            "Henuz paper aday kasa yok. Render **Shell** sekmesinde su komutlari calistir:\n\n"
            "`python -m engine.main lab-generate --limit 40`\n\n"
            "`python -m engine.main lab-backtest --limit 20 --universe 6`"
        )

with tab2:
    backtests = lab_summary.get("recent_backtests") or lab_remote.get("backtests") or []
    if backtests:
        bt_rows = []
        for b in backtests[-30:][::-1]:
            m = b.get("metrics") or {}
            bt_rows.append({
                "Tarif": b.get("recipe_id"),
                "Islem": m.get("n"),
                "WR": f"{100 * float(m.get('win_rate') or 0):.0f}%",
                "PF": m.get("profit_factor"),
                "PnL": m.get("pnl"),
                "Sembol sayisi": m.get("symbols", "-"),
                "Gecti": "Evet" if m.get("passed") else "Hayir",
            })
        st.dataframe(pd.DataFrame(bt_rows), use_container_width=True, hide_index=True)
        passed = sum(1 for b in backtests if (b.get("metrics") or {}).get("passed"))
        st.caption(f"Son {len(backtests)} kayitta {passed} aday esigi gecti.")
    else:
        st.info("Backtest sonucu henuz yok.")

with tab3:
    if lab_open:
        st.subheader("Acik lab pozisyonlari")
        st.dataframe(pd.DataFrame(lab_open), use_container_width=True, hide_index=True)
    else:
        st.info("Lab kasalarinda acik pozisyon yok (henuz sinyal veya giris olmadi).")
    if lab_hist:
        st.subheader("Kapanan lab islemleri")
        dfh = pd.DataFrame(lab_hist).iloc[::-1]
        cols = [c for c in ["exit_time", "symbol", "ledger", "side", "pnl", "close_reason", "strategy"] if c in dfh.columns]
        st.dataframe(dfh[cols], use_container_width=True, hide_index=True)
    if lab_signals:
        st.subheader("Lab sinyalleri")
        sig_rows = [{
            "Sembol": sym,
            "Kasa": s.get("last_ledger"),
            "Yon": s.get("last_side"),
            "Zaman": s.get("last_time"),
            "Sayi": s.get("count"),
        } for sym, s in lab_signals]
        st.dataframe(pd.DataFrame(sig_rows), use_container_width=True, hide_index=True)

with tab4:
    all_c = lab_summary.get("all_candidates") or lab_remote.get("candidates") or []
    rej = [c for c in all_c if c.get("status") == "rejected"]
    if rej:
        st.dataframe(
            pd.DataFrame([{
                "Kasa": c.get("ledger"),
                "Tarif": c.get("recipe_id"),
                "Red zamani": c.get("rejected_at", "-"),
                "Neden": c.get("reject_reason", "-"),
            } for c in rej]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(f"Reddedilen aday yok. (Toplam red sayaci: {rejected_n})")

with tab5:
    lab_logs = [ln for ln in logs if "Lab" in ln or "lab" in ln.lower() or LAB_LEDGER_PREFIX.replace("_", "") in ln]
    if lab_logs:
        st.code("\n".join(lab_logs[-40:]))
    elif logs:
        st.code("\n".join(logs[-40:]))
        st.caption("Lab ozel log yok; genel motor logu gosteriliyor.")
    else:
        st.info("Motor logu bos.")

with st.expander("Ne zaman calisir?"):
    st.markdown(
        f"""
- **Paper motoru** (7/24): Render worker — taranan coinlerde lab aday stratejileri de dener.
- **Tarif uretimi / backtest**: Otomatik degil; Render Shell'den komut calistirilir.
- **Lab aday limiti**: En fazla {LAB_MAX_CANDIDATES} kasa (`Kasa_Lab_001` …).
- **Veri kaynagi**: Motor `{engine_data.get('_source', '-')}` · Lab `{lab_remote.get('_source', '-')}`.
"""
    )

st.caption("Strateji Uretimi v1 — canli durum paneli")
