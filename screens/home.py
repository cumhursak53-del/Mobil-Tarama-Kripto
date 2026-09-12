from datetime import datetime

import pandas as pd
import streamlit as st

from engine.config import DAILY_PNL_TARGET_PCT
from ui_common import (
    build_excel_bytes,
    format_price,
    get_engine_data,
    ledger_daily_performance_rows,
    ledger_live_candidate_rows,
    ledger_summary_rows,
    signal_log_rows,
    source_caption,
)


def render() -> None:
    data = get_engine_data()
    ledgers = data.get("ledgers") or {}
    active = data.get("active_positions") or {}
    history = data.get("history") or []
    history_count = int(data.get("history_count") or len(history))
    sig_log = data.get("signal_log") or {}
    logs = data.get("engine_logs") or []
    equity = float(data.get("equity") or 0)
    cash = float(data.get("balance") or sum(ledgers.values()) if ledgers else 0)
    if not equity:
        equity = cash + sum(float(p.get("margin") or 0) for p in active.values())
    unreal = sum(float(p.get("unrealized_pnl") or 0) for p in active.values())
    closed_pnl = data.get("closed_pnl_total")
    if closed_pnl is None and history:
        closed_pnl = sum(float(h.get("pnl") or 0) for h in history)
    closed_pnl = float(closed_pnl or 0)

    st.title("Canli piyasa simulasyonu")
    st.caption(source_caption(data))

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Toplam ozsermaye", f"${equity:,.2f}")
    c2.metric("Nakit (kasalar)", f"${cash:,.2f}")
    c3.metric("Acik islem", f"{len(active)}")
    c4.metric("Acik PnL", f"${unreal:+,.2f}")
    c5.metric("Kapanan islem", f"{history_count}")
    c6.metric("Kapanan PnL", f"${closed_pnl:+,.2f}")

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
                    "Giris": format_price(p.get("entry_price")),
                    "Anlik": format_price(p.get("current_price")),
                    "SL": format_price(p.get("sl_price")),
                    "TP": format_price(p.get("tp_price")),
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
        df = ledger_summary_rows(ledgers, active, history)
        if not df.empty:
            idle = df[(df["Acik"] == 0) & (df["Kapali"] == 0)]
            st.caption(
                "Acik/Kapali: islem sayisi | Bakiye: kapanan islemlerden sonra kalan | "
                "PnL: kapanan + acik | Total: gercek zamanli (nakit + marjin + acik PnL)"
            )
            if not idle.empty:
                st.warning(
                    f"Hic islem almayan {len(idle)} kasa: "
                    + ", ".join(idle["Kasa"].head(8).tolist())
                    + ("..." if len(idle) > 8 else "")
                )
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Bakiye": st.column_config.NumberColumn(format="$%.2f"),
                    "PnL": st.column_config.NumberColumn(format="$%+.2f"),
                    "Total": st.column_config.NumberColumn(format="$%.2f"),
                },
            )
            st.bar_chart(df.set_index("Kasa")["Total"])

            st.subheader("Gunluk performans (Long / Short)")
            daily = ledger_daily_performance_rows(history, active)
            st.caption(
                f"Kapali islemler cikis gunune; acik islemler giris gunune yazilir. "
                f"Gunluk % = Gunluk_PnL / $100 kasa baslangici. Hedef: >= {DAILY_PNL_TARGET_PCT:.0f}%"
            )
            cands = ledger_live_candidate_rows(daily)
            if not cands.empty:
                st.markdown(f"**Canli aday adaylari (>= {DAILY_PNL_TARGET_PCT:.0f}% en az bir gun)**")
                st.dataframe(
                    cands,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Toplam_PnL": st.column_config.NumberColumn(format="$%+.2f"),
                        "En_iyi_gun_pct": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
            hot = daily[daily["Gunluk_pct"] >= DAILY_PNL_TARGET_PCT] if not daily.empty else daily
            if not hot.empty:
                st.markdown(f"**{DAILY_PNL_TARGET_PCT:.0f}%+ gunler**")
                st.dataframe(
                    hot,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Kapali_PnL": st.column_config.NumberColumn(format="$%+.2f"),
                        "Acik_PnL": st.column_config.NumberColumn(format="$%+.2f"),
                        "Gunluk_PnL": st.column_config.NumberColumn(format="$%+.2f"),
                        "Gunluk_pct": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
            if not daily.empty:
                yon_f = st.selectbox("Yon filtresi", ["Tumu", "LONG", "SHORT"], key="daily_yon_filter")
                show = daily if yon_f == "Tumu" else daily[daily["Yon"] == yon_f]
                st.dataframe(
                    show,
                    use_container_width=True,
                    hide_index=True,
                    height=min(420, 35 * len(show) + 38),
                    column_config={
                        "Kapali_PnL": st.column_config.NumberColumn(format="$%+.2f"),
                        "Acik_PnL": st.column_config.NumberColumn(format="$%+.2f"),
                        "Gunluk_PnL": st.column_config.NumberColumn(format="$%+.2f"),
                        "Gunluk_pct": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
            elif not history and not active:
                st.info("Gunluk performans icin islem gecmisi gerekli.")
        else:
            st.info("Kasa verisi yok.")

    with tab3:
        if history:
            df_h = pd.DataFrame(history)
            for col in ("entry", "exit"):
                if col in df_h.columns:
                    df_h[col] = df_h[col].apply(format_price)
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
        from engine.config import SIGNAL_LOG_RESET_HOUR

        st.caption(
            f"Gunluk oturum: her gece {SIGNAL_LOG_RESET_HOUR:02d}:00 TR'de sifirlanir "
            f"(1d mum baslangicindan beri sinyaller)."
        )
        df_sig = signal_log_rows(sig_log)
        if not df_sig.empty:
            st.dataframe(df_sig, use_container_width=True, hide_index=True)
        else:
            st.info("Sinyal gunlugu bos (oturum basi veya henuz sinyal yok).")

    with tab5:
        if logs:
            st.code("\n".join(logs[-80:]))
        else:
            st.info("Log yok.")


render()
