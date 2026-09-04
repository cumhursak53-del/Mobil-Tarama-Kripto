import pandas as pd
import streamlit as st

from ui_common import get_engine_data, smc_rows, source_caption

SMC_LEDGER = "Kasa_SMC"


def render() -> None:
    data = get_engine_data()
    scan = data.get("smc_scan") or {}
    active = data.get("active_positions") or {}
    history = data.get("history") or []
    ledgers = data.get("ledgers") or {}

    st.title("SMC tarama (LuxAlgo benzeri)")
    st.caption(source_caption(data))
    st.markdown(
        "Motor her coin icin **1D yon + 4H BOS/CHoCH + order block retest + FVG + "
        "likidite sweep + 15m onay** uzerinden skor uretir. "
        "**Skor >= 5** ve **OB retest veya BOS** varsa `Kasa_SMC` isleme girebilir (15m anlik giris)."
    )

    min_score = st.slider("Minimum skor filtresi", 0, 12, 4)
    df = smc_rows(scan)
    if df.empty:
        st.warning(
            "Henuz SMC tarama verisi yok. Render motoru calistiktan sonra "
            "bir tur tamamlaninca burasi dolacak."
        )
    else:
        df = df[df["En_iyi_skor"] >= min_score]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Taranan coin", len(scan))
        c2.metric("Filtre sonrasi", len(df))
        c3.metric("Long adayi (>=5)", int((df["Long_skoru"] >= 5).sum()) if len(df) else 0)
        c4.metric("Short adayi (>=5)", int((df["Short_skoru"] >= 5).sum()) if len(df) else 0)

        tab_a, tab_b, tab_c, tab_d = st.tabs(["Tum liste", "Long", "Short", "Kasa islemleri"])
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


render()
