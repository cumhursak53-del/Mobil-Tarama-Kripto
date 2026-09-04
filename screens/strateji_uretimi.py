"""Strateji uretim hatti — canli durum izleme."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.config import LAB_AUTO, LAB_AUTO_INTERVAL_SEC, LAB_LEDGER_PREFIX, LAB_MAX_CANDIDATES
from ui_common import (
    engine_status,
    load_lab_data,
    minutes_since_update,
    render_sidebar_refresh,
    source_caption,
)


def render() -> None:
    engine_data = render_sidebar_refresh()
    lab_remote = load_lab_data(force_version=st.session_state.get("refresh_version", 0))

    lab_summary = engine_data.get("lab_summary") or {}
    lab_candidates = engine_data.get("lab_candidates") or []
    active = engine_data.get("active_positions") or {}
    history = engine_data.get("history") or []
    logs = engine_data.get("engine_logs") or []
    ledgers = engine_data.get("ledgers") or {}

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
            "pipeline": lab_remote.get("pipeline") or {},
            "research": lab_remote.get("research") or {},
        }
        lab_candidates = [c for c in lab_remote.get("candidates") or [] if c.get("status") == "paper"]

    st.title("Strateji uretimi — canli durum")
    st.caption(source_caption(engine_data))
    st.markdown(
        "Tarif uretimi → backtest → paper aday kasa hattinin durumu. "
        "**Shell gerekmez** — motor otomatik calistirir."
    )

    pipeline = lab_summary.get("pipeline") or lab_remote.get("pipeline") or {}
    pipe_status = pipeline.get("status", "bekleniyor")
    pipe_msg = pipeline.get("last_message") or "-"
    pipe_run = pipeline.get("last_run_at") or "-"
    interval_h = max(1, LAB_AUTO_INTERVAL_SEC // 3600)

    if LAB_AUTO:
        st.info(
            f"Otomasyon **acik**. Motor acilista ve her ~{interval_h} saatte bir tarif uretir, "
            f"backtest yapar, basarili adaylari paper kasaya alir."
        )
    else:
        st.warning("Lab otomasyon kapali (`LAB_AUTO=0`).")

    if pipe_status == "running":
        st.warning(f"Lab pipeline su an calisiyor… {pipe_msg}")
    elif pipe_status == "ok":
        st.success(f"Son otomasyon: {pipe_run} — {pipe_msg}")
    elif pipe_status == "error":
        st.error(f"Son otomasyon hatasi: {pipe_msg}")
    else:
        st.caption(f"Pipeline durumu: {pipe_status}. Deploy sonrasi ilk calisma birkaç dakika surebilir.")

    research = lab_summary.get("research") or lab_remote.get("research") or {}
    flags = engine_data.get("engine_flags") or {}
    research_on = bool(flags.get("research_enabled", research.get("research_enabled", True)))
    gemini_ok = bool(flags.get("gemini_configured", research.get("gemini_configured")))
    has_activity = bool(
        research.get("last_youtube_at") or research.get("last_news_at")
        or (research.get("youtube_recipes") or research.get("news_recipes"))
    )

    if research_on and gemini_ok:
        st.success(
            f"Gemini arastirma **motor uzerinde acik** | YouTube: {research.get('last_youtube_at') or '-'} "
            f"| Haber: {research.get('last_news_at') or '-'} "
            f"| Uretilen: YT {research.get('youtube_recipes', 0)} + haber {research.get('news_recipes', 0)}"
        )
    elif research_on and has_activity:
        st.success("Gemini arastirma calismis (motor log / lab_state kaniti var).")
    elif research_on:
        st.warning(
            "Arastirma acik ama motor **Worker** servisinde `GEMINI_API_KEY` yok veya baglanti basarisiz."
        )
        st.caption(
            "Google AI Studio artik **AQ.** ile baslayan key verir — bu normal ve gecerlidir. "
            "Render Worker → Environment → `GEMINI_API_KEY` = AQ.... key → Save → redeploy."
        )
    else:
        st.caption("Arastirma kapali (`RESEARCH_ENABLED=0`).")

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
            "0. Gemini arastirma",
            gemini_ok and (has_activity or pipe_status in ("ok", "running")),
            f"Motor key: {'var' if gemini_ok else 'YOK'} | YT {research.get('youtube_recipes', 0)} + haber {research.get('news_recipes', 0)}",
        ),
        ("1. Otomasyon motoru", LAB_AUTO and pipe_status in ("ok", "running"), f"Durum: {pipe_status} | Son: {pipe_run}"),
        ("2. Tarif havuzu", recipe_n > 0, f"{recipe_n} tarif" if recipe_n else "Ilk calismada uretilecek"),
        ("3. Backtest", bt_n > 0, f"{bt_n} kayit" if bt_n else "Bekleniyor"),
        ("4. Paper aday", paper_n > 0, f"{paper_n} kasa" if paper_n else "Bekleniyor"),
        ("5. Lab islem", len(lab_open) > 0 or len(lab_hist) > 0, f"{len(lab_open)} acik, {len(lab_hist)} kapali"),
        ("6. GitHub sync", lab_mins is not None and lab_mins <= 30, lab_summary.get("updated_at") or "yok"),
    ]
    for title, ok, detail in steps:
        st.markdown(f"**{'✅' if ok else '⏳'} {title}** — {detail}")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Aday kasalar", "Backtest", "Lab islemleri", "Reddedilenler", "Motor log"]
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
                    "Tarif": c.get("recipe_id"),
                    "Bakiye": f"${bal:.2f}",
                    "Islem": m.get("n", 0),
                    "WR": f"{100 * float(m.get('wr') or 0):.0f}%",
                    "PnL": f"${float(m.get('pnl') or 0):+.2f}",
                    "BT PF": bt.get("profit_factor", "-"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Henuz aday yok; motor otomasyonu birkaç dakika icinde baslayacak.")

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
                    "Gecti": "Evet" if m.get("passed") else "Hayir",
                })
            st.dataframe(pd.DataFrame(bt_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Backtest sonucu henuz yok.")

    with tab3:
        if lab_open:
            st.dataframe(pd.DataFrame(lab_open), use_container_width=True, hide_index=True)
        else:
            st.info("Lab kasalarinda acik pozisyon yok.")
        if lab_hist:
            dfh = pd.DataFrame(lab_hist).iloc[::-1]
            cols = [c for c in ["exit_time", "symbol", "ledger", "side", "pnl", "close_reason"] if c in dfh.columns]
            st.dataframe(dfh[cols], use_container_width=True, hide_index=True)
        if lab_signals:
            st.dataframe(pd.DataFrame([{
                "Sembol": sym, "Kasa": s.get("last_ledger"), "Yon": s.get("last_side"), "Zaman": s.get("last_time"),
            } for sym, s in lab_signals]), use_container_width=True, hide_index=True)

    with tab4:
        all_c = lab_summary.get("all_candidates") or lab_remote.get("candidates") or []
        rej = [c for c in all_c if c.get("status") == "rejected"]
        if rej:
            st.dataframe(pd.DataFrame([{
                "Kasa": c.get("ledger"), "Tarif": c.get("recipe_id"),
                "Neden": c.get("reject_reason", "-"),
            } for c in rej]), use_container_width=True, hide_index=True)
        else:
            st.info(f"Reddedilen aday yok. (Toplam: {rejected_n})")

    with tab5:
        lab_logs = [ln for ln in logs if "Lab" in ln or "lab" in ln.lower()]
        st.code("\n".join(lab_logs[-40:] if lab_logs else logs[-40:] or ["Log yok"]))


render()
