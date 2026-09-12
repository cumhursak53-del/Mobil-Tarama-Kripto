import streamlit as st

from engine.trade_analysis import ledger_analysis_summary
from ui_common import get_engine_data, post_exit_analysis_rows, post_exit_watch_rows, source_caption


def render() -> None:
    st.title("Islem Analizi")
    st.caption("Kapanan islemler 24 saat daha izlenir; SL/TP kararlari ve kacirilan firsatlar analiz edilir.")
    data = get_engine_data()
    st.caption(source_caption(data))

    log = data.get("post_exit_log") or []
    watch = data.get("post_exit_watchlist") or []

    sl_items = [x for x in log if x.get("close_reason") == "SL"]
    tp_items = [x for x in log if x.get("close_reason") == "TP"]
    sl_tight = sum(1 for x in sl_items if x.get("sl_verdict") == "too_tight")
    sl_ok = sum(1 for x in sl_items if x.get("sl_verdict") == "correct")
    tp_early = sum(1 for x in tp_items if x.get("tp_verdict") == "too_early")
    tp_ok = sum(1 for x in tp_items if x.get("tp_verdict") == "correct")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Analiz edilen", len(log))
    c2.metric("Aktif izleme", len(watch))
    c3.metric("SL siki", sl_tight)
    c4.metric("SL dogru", sl_ok)
    c5.metric("TP erken", tp_early)

    if watch:
        st.subheader("Aktif izleme (24s)")
        st.dataframe(
            post_exit_watch_rows(watch),
            use_container_width=True,
            hide_index=True,
        )

    if not log:
        st.info("Henuz tamamlanmis islem analizi yok. Islem kapandiktan 24 saat sonra sonuclar burada gorunur.")
        return

    st.subheader("Kasa ozeti")
    summary = ledger_analysis_summary(log)
    if not summary.empty:
        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Detay analiz")
    df = post_exit_analysis_rows(log)
    kasalar = ["Tumu"] + sorted(df["Kasa"].dropna().unique().tolist())
    kapanis = ["Tumu", "SL", "TP", "PARTIAL_TP"]
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
        show = show[
            (show["SL_karar"] == verdict_f) | (show["TP_karar"] == verdict_f)
        ]

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

    if tp_ok:
        st.caption(f"TP dogru karar: {tp_ok} islem")
