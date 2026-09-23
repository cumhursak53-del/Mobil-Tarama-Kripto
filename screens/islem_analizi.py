import streamlit as st

from engine.signal_analysis import strategy_signal_summary
from engine.trade_analysis import ledger_analysis_summary
from ui_common import (
    get_engine_data,
    post_exit_analysis_rows,
    post_exit_watch_rows,
    signal_outcome_rows,
    signal_watch_rows,
    source_caption,
)


def _render_trade_analysis(data: dict) -> None:
    log = data.get("post_exit_log") or []
    watch = data.get("post_exit_watchlist") or []

    sl_items = [x for x in log if x.get("close_reason") == "SL"]
    tp_items = [x for x in log if x.get("close_reason") == "TP"]
    sl_tight = sum(1 for x in sl_items if x.get("sl_verdict") == "too_tight")
    sl_ok = sum(1 for x in sl_items if x.get("sl_verdict") == "correct")
    tp_early = sum(1 for x in tp_items if x.get("tp_verdict") == "too_early")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Analiz edilen islem", len(log))
    c2.metric("Aktif islem izleme", len(watch))
    c3.metric("SL siki", sl_tight)
    c4.metric("SL dogru", sl_ok)
    c5.metric("TP erken", tp_early)

    if watch:
        st.subheader("Aktif islem izleme (24s)")
        st.dataframe(post_exit_watch_rows(watch), use_container_width=True, hide_index=True)

    if not log:
        st.info("Henuz tamamlanmis islem analizi yok. Islem kapandiktan 24 saat sonra sonuclar burada gorunur.")
        return

    st.subheader("Kasa ozeti")
    summary = ledger_analysis_summary(log)
    if not summary.empty:
        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Islem detay")
    df = post_exit_analysis_rows(log)
    kasalar = ["Tumu"] + sorted(df["Kasa"].dropna().unique().tolist())
    kapanis = ["Tumu", "SL", "TP", "PARTIAL_TP", "INVALIDATED"]
    col_a, col_b, col_c = st.columns(3)
    kasa_f = col_a.selectbox("Kasa", kasalar, key="analiz_kasa")
    kapanis_f = col_b.selectbox("Kapanis", kapanis, key="analiz_kapanis")
    verdict_opts = ["Tumu", "too_tight", "correct", "too_early", "neutral"]
    verdict_f = col_c.selectbox("Karar", verdict_opts, key="analiz_verdict")

    show = df.copy()
    if kasa_f != "Tumu":
        show = show[show["Kasa"] == kasa_f]
    if kapanis_f != "Tumu":
        show = show[show["Kapanis"] == kapanis_f]
    if verdict_f != "Tumu":
        show = show[(show["SL_karar"] == verdict_f) | (show["TP_karar"] == verdict_f)]

    st.dataframe(
        show,
        use_container_width=True,
        hide_index=True,
        height=min(520, 35 * len(show) + 38),
        column_config={
            "PnL": st.column_config.NumberColumn(format="$%+.2f"),
            "MFE_islem": st.column_config.NumberColumn(format="%.2fR"),
            "MAE_islem": st.column_config.NumberColumn(format="%.2fR"),
            "MFE_sonrasi": st.column_config.NumberColumn(format="$%+.2f"),
            "Kacirilan_USD": st.column_config.NumberColumn(format="$%+.2f"),
            "Optimal_fark_pct": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )


def _render_signal_analysis(data: dict) -> None:
    flags = data.get("engine_flags") or {}
    if not flags.get("signal_analysis") and "signal_watchlist" not in data:
        st.warning(
            "Bu motor surumu sinyal analizini desteklemiyor (eski kod). "
            "Hostinger: git pull + deploy_vps.sh | Render: worker yeniden deploy."
        )
    log = data.get("signal_outcome_log") or []
    watch = data.get("signal_watchlist") or []

    correct = sum(1 for x in log if x.get("verdict") == "correct")
    wrong = sum(1 for x in log if x.get("verdict") == "wrong")
    tp_hit = sum(1 for x in log if x.get("outcome") == "tp_hit")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Analiz edilen sinyal", len(log))
    c2.metric("Aktif sinyal izleme", len(watch))
    c3.metric("Dogru / guclu", correct)
    c4.metric("Yanlis / zayif", wrong)

    if watch:
        st.subheader("Aktif sinyal izleme (24s)")
        st.caption("Her benzersiz sembol+strateji+yon icin bir kez izleme baslar; tekrarlayan loglar sayilmaz.")
        st.dataframe(signal_watch_rows(watch), use_container_width=True, hide_index=True)

    if not log:
        st.info(
            "Henuz tamamlanmis sinyal analizi yok. Motor sinyal urettikten 24 saat sonra "
            "TP/SL ve yon dogrulugu burada raporlanir."
        )
        return

    st.subheader("Strateji ozeti")
    summary = strategy_signal_summary(log)
    if not summary.empty:
        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Sinyal detay")
    st.caption("Tum tamamlanan analizler — satir limiti yok")
    df = signal_outcome_rows(log)
    strats = ["Tumu"] + sorted(df["Strateji"].dropna().unique().tolist())
    verdicts = ["Tumu", "correct", "wrong", "neutral"]
    outcomes = ["Tumu"] + sorted(df["Sonuc"].dropna().unique().tolist())
    col_a, col_b, col_c = st.columns(3)
    strat_f = col_a.selectbox("Strateji", strats, key="sig_strat")
    verdict_f = col_b.selectbox("Karar", verdicts, key="sig_verdict")
    outcome_f = col_c.selectbox("Sonuc", outcomes, key="sig_outcome")

    show = df.copy()
    if strat_f != "Tumu":
        show = show[show["Strateji"] == strat_f]
    if verdict_f != "Tumu":
        show = show[show["Karar"] == verdict_f]
    if outcome_f != "Tumu":
        show = show[show["Sonuc"] == outcome_f]

    st.caption(f"{len(show)} kayit gosteriliyor")
    st.dataframe(
        show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Hipotetik_PnL": st.column_config.NumberColumn(format="$%+.2f"),
            "24s_hareket_pct": st.column_config.NumberColumn(format="%.2f%%"),
            "MFE_R": st.column_config.NumberColumn(format="%.2fR"),
            "MAE_R": st.column_config.NumberColumn(format="%.2fR"),
        },
    )


def render() -> None:
    st.title("Sinyal ve Islem Analiz Merkezi")
    st.caption(
        "Sinyaller ve kapanan islemler 24 saat izlenir; TP/SL, yon dogrulugu ve strateji performansi otomatik analiz edilir."
    )
    data = get_engine_data()
    st.caption(source_caption(data))

    tab_sig, tab_trade = st.tabs(["Sinyal analizi (24s)", "Islem analizi (24s)"])
    with tab_sig:
        _render_signal_analysis(data)
    with tab_trade:
        _render_trade_analysis(data)
