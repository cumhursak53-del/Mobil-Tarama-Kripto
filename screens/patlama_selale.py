import pandas as pd
import streamlit as st

from engine.config import PATLAMA_LEDGER
from ui_common import patlama_rows, render_sidebar_refresh, source_caption


def render() -> None:
    data = render_sidebar_refresh()
    scan = data.get("patlama_selale_scan") or {}
    active = data.get("active_positions") or {}
    history = data.get("history") or []
    ledgers = data.get("ledgers") or {}

    st.title("Patlama / Selale tarama")
    st.caption(source_caption(data))
    st.markdown(
        "Motor her coin icin **1D yon + 4H setup + 1H kirilim + hacim + 15M tetik** "
        "uzerinden 0-7 arasi skor uretir. **Skor >= 4** ise `Kasa_PatlamaSelale` isleme girebilir."
    )

    min_score = st.slider("Minimum skor filtresi", 0, 7, 3)
    df = patlama_rows(scan)
    if df.empty:
        st.warning(
            "Henuz tarama verisi yok. Render motoru calistiktan sonra "
            "bir tur tamamlaninca burasi dolacak."
        )
    else:
        df = df[df["En_iyi_skor"] >= min_score]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Taranan coin", len(scan))
        c2.metric("Filtre sonrasi", len(df))
        c3.metric("Patlama adayi (>=4)", int((df["Patlama_skoru"] >= 4).sum()) if len(df) else 0)
        c4.metric("Selale adayi (>=4)", int((df["Selale_skoru"] >= 4).sum()) if len(df) else 0)

        tab_a, tab_b, tab_c, tab_d = st.tabs(["Tum liste", "Patlama", "Selale", "Kasa islemleri"])
        with tab_a:
            st.dataframe(df, use_container_width=True, hide_index=True, height=520)
        with tab_b:
            sub = df[df["Patlama_skoru"] >= min_score].sort_values("Patlama_skoru", ascending=False)
            st.dataframe(sub, use_container_width=True, hide_index=True, height=520)
        with tab_c:
            sub = df[df["Selale_skoru"] >= min_score].sort_values("Selale_skoru", ascending=False)
            st.dataframe(sub, use_container_width=True, hide_index=True, height=520)
        with tab_d:
            kasa_bal = float(ledgers.get(PATLAMA_LEDGER, 100))
            st.metric("Kasa bakiyesi", f"${kasa_bal:,.2f}", delta=f"{kasa_bal - 100:+.2f}")
            open_rows = [
                p for p in active.values()
                if isinstance(p, dict) and p.get("ledger_name") == PATLAMA_LEDGER
            ]
            if open_rows:
                st.dataframe(pd.DataFrame(open_rows), use_container_width=True, hide_index=True)
            else:
                st.info("Patlama/Selale kasasinda acik islem yok.")
            hist = [h for h in history if h.get("ledger") == PATLAMA_LEDGER]
            if hist:
                st.subheader("Kapanan islemler")
                st.dataframe(pd.DataFrame(hist).iloc[::-1], use_container_width=True, hide_index=True)


render()
