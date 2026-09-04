from datetime import datetime

import pandas as pd
import streamlit as st

from ui_common import build_excel_bytes, get_engine_data, source_caption


def render() -> None:
    data = get_engine_data()
    ledgers = data.get("ledgers") or {}
    active = data.get("active_positions") or {}
    history = data.get("history") or []
    sig_log = data.get("signal_log") or {}
    logs = data.get("engine_logs") or []
    equity = float(data.get("equity") or 0)
    cash = float(data.get("balance") or sum(ledgers.values()) if ledgers else 0)
    if not equity:
        equity = cash + sum(float(p.get("margin") or 0) for p in active.values())
    unreal = sum(float(p.get("unrealized_pnl") or 0) for p in active.values())

    st.title("Canli piyasa simulasyonu")
    st.caption(source_caption(data))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Toplam ozsermaye", f"${equity:,.2f}")
    c2.metric("Nakit (kasalar)", f"${cash:,.2f}")
    c3.metric("Acik islem", f"{len(active)}")
    c4.metric("Acik PnL", f"${unreal:+,.2f}")
    c5.metric("Kapanan islem", f"{len(history)}")

    xlsx = build_excel_bytes(data)
    st.download_button(
        label="Excel indir (.xlsx)",
        data=xlsx,
        file_name=f"krpito_rapor_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Acik pozisyonlar", "Kasalar", "Islem gecmisi", "Sinyal gunlugu", "Motor log"]
    )

    with tab1:
        if active:
            rows = []
            for key, p in active.items():
                rows.append({
                    "Sembol": p.get("symbol", key),
                    "Kasa": p.get("ledger_name", "-"),
                    "Yon": p.get("side"),
                    "Giris": p.get("entry_price"),
                    "Anlik": p.get("current_price"),
                    "SL": p.get("sl_price"),
                    "TP": p.get("tp_price"),
                    "ROE %": p.get("roe_pct"),
                    "Acik PnL": p.get("unrealized_pnl"),
                    "Marjin": p.get("margin"),
                    "Kaldirac": p.get("leverage"),
                    "Strateji": p.get("strategy"),
                    "Giris zamani": p.get("entry_time"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Acik pozisyon yok.")

    with tab2:
        if ledgers:
            start = 100.0
            rows = [{"Kasa": k, "Bakiye": v, "PnL": v - start} for k, v in ledgers.items()]
            df = pd.DataFrame(rows).sort_values("Bakiye", ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.bar_chart(df.set_index("Kasa")["Bakiye"])
        else:
            st.info("Kasa verisi yok.")

    with tab3:
        if history:
            df_h = pd.DataFrame(history)
            cols = [
                c for c in [
                    "exit_time", "symbol", "ledger", "side", "entry", "exit",
                    "pnl", "r", "close_reason", "strategy",
                ] if c in df_h.columns
            ]
            st.dataframe(df_h[cols].iloc[::-1], use_container_width=True, hide_index=True)
            curve = data.get("equity_curve") or []
            if curve:
                cdf = pd.DataFrame(curve)
                if "time" in cdf.columns and "equity" in cdf.columns:
                    st.line_chart(cdf.set_index("time")["equity"])
        else:
            st.info("Henuz kapanan islem yok.")

    with tab4:
        if sig_log:
            rows = []
            for sym, s in sig_log.items():
                strats = s.get("strategies") or []
                if isinstance(strats, list):
                    strats = ", ".join(strats[-6:])
                rows.append({
                    "Sembol": sym,
                    "Sinyal": s.get("count", 0),
                    "Son yon": s.get("last_side", "-"),
                    "Kasa": s.get("last_ledger", "-"),
                    "Zaman": s.get("last_time", "-"),
                    "Stratejiler": strats,
                })
            st.dataframe(
                pd.DataFrame(rows).sort_values("Sinyal", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Sinyal gunlugu bos.")

    with tab5:
        if logs:
            st.code("\n".join(logs[-80:]))
        else:
            st.info("Log yok.")


render()
