import json
import os
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

STATE_FILE = "state.json"

st.set_page_config(page_title="Futures Mobil Engine", page_icon="📈", layout="wide")

def load_data():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"balance": 100.0, "active_positions": {}, "history": [], "signal_log": {}}

data = load_data()

# Üst Bilgi Kartları
st.title("📈 Futures Kar Öngörülü Engine")

active_pos = data.get("active_positions", {})
history = data.get("history", [])
allocated_margin = sum(p["margin"] for p in active_pos.values())
total_equity = data.get("balance", 100.0) + allocated_margin

col1, col2, col3 = st.columns(3)
col1.metric("Kümülatif Kasa", f"${total_equity:.2f}")
col2.metric("Açık Pozisyon", f"{len(active_pos)} / 10")
col3.metric("Tamamlanan İşlem", f"{len(history)}")

st.divider()

# Sekme Yapısı
tab1, tab2, tab3 = st.tabs(["📊 Açık Pozisyonlar", "📜 İşlem Geçmişi", "🎯 Sinyal Günlüğü"])

with tab1:
    st.subheader("Canlı Pozisyonlar")
    if active_pos:
        pos_list = []
        for sym, p in active_pos.items():
            pos_list.append({
                "Sembol": sym,
                "Yön": p["side"],
                "Giriş Fiyatı": f"${p['entry_price']:.4f}",
                "Pik Fiyat": f"${p.get('peak_price', p['entry_price']):.4f}",
                "Hedef ROE": f"%{p.get('target_roe', 0):.1f}",
                "Durum": "🏹 Trailing" if p.get("trailing_active") else "⏳ Bekliyor",
                "Stratejiler": p.get("strategies", "-")
            })
        st.dataframe(pd.DataFrame(pos_list), use_container_width=True)
    else:
        st.info("Şu anda açık pozisyon bulunmuyor.")

    # Kasa Büyüme Grafiği
    st.subheader("Kasa Büyüme Grafiği")
    if history:
        df_hist = pd.DataFrame(history)
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df_hist["exit_time"], df_hist["new_balance"], color="#2ecc71", marker="o", linewidth=2)
        ax.set_facecolor("#0e1117")
        fig.patch.set_facecolor("#0e1117")
        ax.tick_params(colors="white")
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else:
        st.write("Henüz kapanan işlem grafiği yok.")

with tab2:
    st.subheader("Detaylı İşlem Geçmişi")
    if history:
        df_h = pd.DataFrame(history)[["entry_time", "exit_time", "symbol", "side", "entry", "exit", "pnl", "close_reason", "new_balance"]]
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
    else:
        st.info("İşlem geçmişi boş.")

with tab3:
    st.subheader("İşlem Eşiğini Geçen Sinyaller")
    sig_log = data.get("signal_log", {})
    if sig_log:
        sig_list = []
        for sym, s in sig_log.items():
            sig_list.append({
                "Sembol": sym,
                "Sinyal Sayısı": s.get("count", 0),
                "Son Yön": s.get("last_side", "-"),
                "Son Skor": s.get("last_score", 0),
                "Beklenen ROE": f"%{s.get('last_roe', 0):.1f}",
                "Son Zaman": s.get("last_time", "-"),
                "Stratejiler": s.get("strategies", "-")
            })
        df_sig = pd.DataFrame(sig_list).sort_values(by="Sinyal Sayısı", ascending=False)
        st.dataframe(df_sig, use_container_width=True)
    else:
        st.info("Henüz sinyal günlüğü oluşmadı.")