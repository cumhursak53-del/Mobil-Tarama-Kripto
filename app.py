import json
import os
import requests
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

RENDER_API_URL = "https://mobil-tarama-kripto.onrender.com"

st.set_page_config(page_title="Futures Mobil Engine", page_icon="📈", layout="wide")

def load_data():
    try:
        res = requests.get(RENDER_API_URL, timeout=6)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    
    if os.path.exists("durum.json"):
        try:
            with open("durum.json", "r") as f:
                return json.load(f)
        except Exception:
            pass
            
    return {"balance": 100.0, "active_positions": {}, "history": [], "signal_log": {}, "engine_logs": []}

data = load_data()

st.title("📈 Futures Kar Öngörülü Engine")

active_pos = data.get("active_positions", {})
history = data.get("history", [])
allocated_margin = sum(p["margin"] for p in active_pos.values())
total_equity = data.get("balance", 100.0) + allocated_margin

col1, col2, col3 = st.columns(3)
col1.metric("Kümülatif Kasa", f"${total_equity:.2f}")
col2.metric("Açık Pozisyon", f"{len(active_pos)} / 10")
col3.metric("Tamamlanan İşlem", f"{len(history)}")

if st.button("🔄 Verileri Şimdi Yenile"):
    st.rerun()

st.divider()

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Açık Pozisyonlar & Canlı PnL", 
    "📜 İşlem Geçmişi", 
    "🎯 Sinyal Günlüğü", 
    "🖥️ Canlı Bot Logları"
])

with tab1:
    st.subheader("Canlı Pozisyonlar & Anlık Kâr/Zarar (PnL)")
    if active_pos:
        pos_list = []
        total_unrealized = 0.0
        
        for sym, p in active_pos.items():
            entry = p["entry_price"]
            current = p.get("current_price", entry)
            side = p["side"]
            margin = p["margin"]
            leverage = 10
            
            # Anlık Kâr / Zarar Hesaplaması
            ratio = (current - entry) / entry if side == "BUY" else (entry - current) / entry
            pnl = margin * leverage * ratio
            roe = ratio * leverage * 100
            total_unrealized += pnl

            pos_list.append({
                "Sembol": sym,
                "Yön": side,
                "Giriş Fiyatı": f"${entry:,.4f}",
                "Canlı Fiyat": f"${current:,.4f}",
                "Anlık PnL ($)": f"${pnl:+.2f}",
                "Anlık ROE (%)": f"%{roe:+.2f}",
                "Pik Fiyat": f"${p.get('peak_price', entry):,.4f}",
                "Durum": "🏹 Trailing Stop" if p.get("trailing_active") else "⏳ Takipte",
                "Stratejiler": p.get("strategies", "-")
            })
            
        st.dataframe(pd.DataFrame(pos_list), use_container_width=True)
        
        # Anlık Toplam Kâr/Zarar Göstergesi
        color = "green" if total_unrealized >= 0 else "red"
        st.markdown(f"### Toplam Anlık Unrealized PnL: :{color}[${total_unrealized:+.2f}]")
    else:
        st.info("Şu anda açık pozisyon bulunmuyor. Engine 15m tarama yapıyor...")

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
        st.write("Henüz kapanan işlem grafiği oluşmadı.")

with tab2:
    st.subheader("Detaylı İşlem Geçmişi")
    if history:
        df_h = pd.DataFrame(history)[["entry_time", "exit_time", "symbol", "side", "entry", "exit", "pnl", "close_reason", "new_balance"]]
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
    else:
        st.info("İşlem geçmişi boş.")

with tab3:
    st.subheader("İşlem Eşiğini Geçen Elit Sinyaller (≥ 85 / ≤ -85)")
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
        st.info("Henüz eşik üstü sinyal günlüğü kayıt altına alınmadı.")

with tab4:
    st.subheader("🖥️ Render Sunucu Canlı Tarama Logları")
    logs = data.get("engine_logs", [])
    if logs:
        log_text = "\n".join(reversed(logs[-50:]))
        st.code(log_text, language="text")
    else:
        st.warning("Sunucudan henüz log akışı alınamadı...")
