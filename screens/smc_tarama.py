import pandas as pd
import streamlit as st

from engine.context import indicate_frame
from engine.data import fetch_klines
from engine.gemini_client import gemini_available, generate_smc_commentary, generate_smc_vision_commentary
from structure.smc import analyze_smc
from ui.chart_export import fig_to_png_bytes
from ui.smc_chart import build_smc_chart
from ui_common import get_engine_data, smc_rows, source_caption

SMC_LEDGER = "Kasa_SMC"
CHART_TFS = ("15m", "1h", "4h", "1d")
HTF_MAP = {"15m": "4h", "1h": "4h", "4h": "1d", "1d": "1w"}


def _load_chart_frames(symbol: str, tf: str) -> pd.DataFrame:
    df = fetch_klines(symbol, tf, limit=200)
    return indicate_frame(df)


def _render_chart_tab(symbols: list[str], scan: dict) -> None:
    st.subheader("Grafik incelemesi")
    st.caption("Canli veri + SMC zone overlay, swing/BOS etiketleri, HTF panel, Gemini vision.")

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        default_sym = symbols[0] if symbols else "BTCUSDT"
        symbol = st.selectbox("Sembol", symbols or [default_sym], index=0)
    with c2:
        tf = st.selectbox("Timeframe", CHART_TFS, index=2)
    with c3:
        show_htf = st.checkbox("HTF panel", value=True)
    with c4:
        gemini_mode = st.selectbox(
            "Gemini",
            ["Kapali", "Metin", "Vision (grafik)"],
            index=0,
            disabled=not gemini_available(),
        )

    if st.button("Grafigi yukle", type="primary"):
        st.session_state["smc_chart_sym"] = symbol
        st.session_state["smc_chart_tf"] = tf
        st.session_state["smc_chart_htf"] = show_htf
        st.session_state["smc_chart_gemini"] = gemini_mode

    sym = st.session_state.get("smc_chart_sym", symbol)
    chart_tf = st.session_state.get("smc_chart_tf", tf)
    want_htf = st.session_state.get("smc_chart_htf", show_htf)
    gemini_mode = st.session_state.get("smc_chart_gemini", "Kapali")

    try:
        df = _load_chart_frames(sym, chart_tf)
        if df.empty or len(df) < 30:
            st.warning(f"{sym} {chart_tf} icin yeterli mum verisi alinamadi.")
            return

        analysis = analyze_smc(df)
        htf_df = None
        htf_analysis = None
        if want_htf:
            htf_tf = HTF_MAP.get(chart_tf, "4h")
            try:
                htf_df = _load_chart_frames(sym, htf_tf)
                if htf_df is not None and len(htf_df) >= 30:
                    htf_analysis = analyze_smc(htf_df)
            except Exception:
                htf_df = None

        title = (
            f"{sym} {chart_tf} | L:{analysis.long_score} S:{analysis.short_score} | "
            f"Grade L:{analysis.setup_grade_long} S:{analysis.setup_grade_short}"
        )
        fig = build_smc_chart(df, analysis, title=title, htf_df=htf_df, htf_analysis=htf_analysis)
        st.plotly_chart(fig, use_container_width=True)

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Long skor", analysis.long_score)
        m2.metric("Short skor", analysis.short_score)
        m3.metric("Long grade", analysis.setup_grade_long)
        m4.metric("Confluence L", analysis.confluence_long)
        m5.metric("Swing int/ext", f"{analysis.internal_swing_n}/{analysis.external_swing_n}")
        m6.metric("Session", analysis.session)

        with st.expander("SMC detay", expanded=False):
            st.json(analysis.to_dict())

        scan_row = scan.get(sym) if isinstance(scan, dict) else None
        if scan_row:
            st.info(
                f"Motor tarama: skor {scan_row.get('best_score', '-')} | "
                f"yon {scan_row.get('best_side', '-')} | "
                f"grade L:{scan_row.get('setup_grade_long', '-')} S:{scan_row.get('setup_grade_short', '-')}"
            )

        if gemini_mode == "Metin":
            with st.spinner("Gemini metin yorumu..."):
                comment = generate_smc_commentary(
                    symbol=sym, timeframe=chart_tf, analysis=analysis.to_dict(),
                )
            st.markdown("#### Gemini SMC yorumu (metin)")
            st.markdown(comment)
        elif gemini_mode == "Vision (grafik)":
            png = fig_to_png_bytes(fig)
            if png is None:
                st.warning("Grafik PNG export icin kaleido gerekli. Metin moduna dusuluyor.")
                comment = generate_smc_commentary(
                    symbol=sym, timeframe=chart_tf, analysis=analysis.to_dict(),
                )
            else:
                with st.spinner("Gemini vision grafik analizi..."):
                    comment = generate_smc_vision_commentary(
                        symbol=sym,
                        timeframe=chart_tf,
                        analysis=analysis.to_dict(),
                        image_bytes=png,
                    )
                st.image(png, caption=f"{sym} {chart_tf} SMC grafik", use_container_width=True)
            st.markdown("#### Gemini SMC yorumu (vision)")
            st.markdown(comment)

    except Exception as e:
        st.error(f"Grafik yuklenemedi: {e}")


def render() -> None:
    data = get_engine_data()
    scan = data.get("smc_scan") or {}
    active = data.get("active_positions") or {}
    history = data.get("history") or []
    ledgers = data.get("ledgers") or {}

    st.title("SMC tarama (LuxAlgo benzeri)")
    st.caption(source_caption(data))
    st.markdown(
        "Motor **1W+1D+4H+1H+15m** SMC checklist calistirir. "
        "**Grafik inceleme** sekmesinde zone overlay, BOS etiketleri, HTF panel ve Gemini vision kullanin."
    )

    min_score = st.slider("Minimum skor filtresi", 0, 15, 5)
    grade_filter = st.selectbox("Minimum setup grade", ["Hepsi", "C+", "B+", "A only"], index=2)
    df = smc_rows(scan)
    symbols = df["Sembol"].tolist() if not df.empty else sorted(scan.keys())

    if df.empty:
        st.warning(
            "Henuz SMC tarama verisi yok. Render motoru calistiktan sonra "
            "bir tur tamamlaninca burasi dolacak."
        )
        tab_chart, = st.tabs(["Grafik inceleme"])
        with tab_chart:
            _render_chart_tab(["BTCUSDT", "ETHUSDT", "SOLUSDT"], scan)
    else:
        df = df[df["En_iyi_skor"] >= min_score]
        if grade_filter == "C+":
            df = df[(df["Long_grade"].isin(["A", "B", "C"])) | (df["Short_grade"].isin(["A", "B", "C"]))]
        elif grade_filter == "B+":
            df = df[(df["Long_grade"].isin(["A", "B"])) | (df["Short_grade"].isin(["A", "B"]))]
        elif grade_filter == "A only":
            df = df[(df["Long_grade"] == "A") | (df["Short_grade"] == "A")]
        symbols = df["Sembol"].tolist() if not df.empty else symbols

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Taranan coin", len(scan))
        c2.metric("Filtre sonrasi", len(df))
        c3.metric("Long adayi (>=5)", int((df["Long_skoru"] >= 5).sum()) if len(df) else 0)
        c4.metric("Short adayi (>=5)", int((df["Short_skoru"] >= 5).sum()) if len(df) else 0)

        tab_a, tab_b, tab_c, tab_d, tab_chart = st.tabs(
            ["Tum liste", "Long", "Short", "Kasa islemleri", "Grafik inceleme"]
        )
        with tab_a:
            st.dataframe(df, use_container_width=True, hide_index=True, height=520)
        with tab_b:
            sub = df[df["Long_skoru"] >= min_score].sort_values("Long_skoru", ascending=False)
            st.dataframe(sub, use_container_width=True, hide_index=True, height=520)
        with tab_c:
            sub = df[df["Short_skoru"] >= min_score].sort_values("Short_skoru", ascending=False)
            st.dataframe(sub, use_container_width=True, hide_index=True, height=520)
        with tab_d:
            kasa_bal = float(ledgers.get(SMC_LEDGER, 100))
            st.metric("Kasa bakiyesi", f"${kasa_bal:,.2f}", delta=f"{kasa_bal - 100:+.2f}")
            open_rows = [
                p for p in active.values()
                if isinstance(p, dict) and p.get("ledger_name") == SMC_LEDGER
            ]
            if open_rows:
                st.dataframe(pd.DataFrame(open_rows), use_container_width=True, hide_index=True)
            else:
                st.info("SMC kasasinda acik islem yok.")
            hist = [h for h in history if h.get("ledger") == SMC_LEDGER]
            if hist:
                st.subheader("Kapanan islemler")
                st.dataframe(pd.DataFrame(hist).iloc[::-1], use_container_width=True, hide_index=True)
        with tab_chart:
            _render_chart_tab(symbols, scan)


render()
