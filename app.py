import streamlit as st
import pandas as pd
import json
import os
import requests

st.set_page_config(page_title="Kurumsal MTF Bot", page_icon="🤖", layout="wide")

API_URL = "http://127.0.0.1:10000"

@st.cache_data(ttl=5)
def fetch_data():
    try:
        res = requests.get(API_URL, timeout=3)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    
    if os.path.exists("durum.json"):
        try:
            with open("durum.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

data = fetch_data()

if not data:
    st.warning("📡 Veri bekleniyor veya durum.json bulunamadı...")
    st.stop()

ledgers = data.get("ledgers", {})
active_pos = data.get("active_positions", {})
history = data.get("history", [])
signals = data.get("signal_log", {})
logs = data.get("engine_logs", [])

st.title("🤖 Kurumsal Kripto Fon Yönetimi")

# Sekmeler
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💰 Kasa Özeti", 
    f"🟢 Aktif İşlemler ({len(active_pos)})", 
    "📚 İşlem Geçmişi", 
    "🎯 Günlük Sinyaller", 
    "🖥️ Sistem Logları"
])

with tab1:
    st.subheader("Bölünmüş Kasa (Sub-Ledger) Performansı")
    if ledgers:
        # Aktif marjinleri kasalara geri ekleyerek toplam fonu bulalım
        total_funds = sum(ledgers.values())
        for pos in active_pos.values():
            total_funds += pos.get("margin", 0)
            
        st.metric("Toplam Fon Büyüklüğü (Aktif Marjinler Dahil)", f"${total_funds:.2f}")
        st.divider()
        
        cols = st.columns(4)
        idx = 0
        for name, balance in ledgers.items():
            clean_name = name.replace("Kasa_", "").replace("_", " ")
            with cols[idx % 4]:
                st.metric(clean_name, f"${balance:.2f}")
            idx += 1
    else:
        st.info("Kasa verisi henüz oluşmadı.")

with tab2:
    st.subheader("Açık Pozisyonlar ve Derinlik (MFE/MAE) Takibi")
    if active_pos:
        df_active = []
        for sym, pos in active_pos.items():
            df_active.append({
                "Coin": sym,
                "Yön": "🟩 LONG" if pos["side"] == "BUY" else "🟥 SHORT",
                "Kasa": pos.get("ledger_name", "-").replace("Kasa_", "").replace("_", " "),
                "Strateji": pos.get("strategy", "-").replace("[STRAT: ", "").replace("]", ""),
                "Giriş Fiyatı": f"${pos['entry_price']:.4f}",
                "Anlık Fiyat": f"${pos.get('current_price', pos['entry_price']):.4f}",
                "MFE (Zirve Kâr)": f"${pos.get('max_reached_price', pos['entry_price']):.4f}",
                "MAE (Dip Zarar)": f"${pos.get('min_reached_price', pos['entry_price']):.4f}",
                "Marjin": f"${pos['margin']:.2f}",
            })
        st.dataframe(pd.DataFrame(df_active), use_container_width=True)
    else:
        st.success("Şu an açık pozisyon bulunmuyor. Sistem pusu modunda.")

with tab3:
    st.subheader("Kapanmış İşlemler (Kâr/Zarar ve Fiyat Sınırları Analizi)")
    if history:
        df_hist = []
        for h in reversed(history[-50:]): # Son 50 işlem
            df_hist.append({
                "Tarih": h.get("exit_time", "-"),
                "Coin": h["symbol"],
                "Yön": "🟩 LONG" if h["side"] == "BUY" else "🟥 SHORT",
                "Kasa": h.get("ledger", "-").replace("Kasa_", "").replace("_", " "),
                "Net PnL": f"${h['pnl']:.2f}",
                "Kapanış Nedeni": h.get("close_reason", "-").replace("🛑", "").replace("🏹", "").strip(),
                "Giriş": f"${h['entry']:.4f}",
                "Çıkış": f"${h['exit']:.4f}",
                "MFE (Çıktığı En Yüksek)": f"${h.get('mfe_price', h['entry']):.4f}",
                "MAE (Düştüğü En Düşük)": f"${h.get('mae_price', h['entry']):.4f}"
            })
        df = pd.DataFrame(df_hist)
        
        # PnL'e göre yeşil/kırmızı renklendirme
        def color_pnl(val):
            try:
                color = '#00FF00' if float(val.replace('$', '')) > 0 else '#FF0000'
            except:
                color = 'white'
            return f'color: {color}'
            
        st.dataframe(df.style.map(color_pnl, subset=['Net PnL']), use_container_width=True)
    else:
        st.info("Henüz kapanmış işlem bulunmuyor.")

with tab4:
    st.subheader(f"Günlük Sinyal Radarı ({data.get('signal_date', 'Bugün')})")
    st.caption("🔔 Bu liste her gece yarısı otomatik olarak sıfırlanır. Yalnızca günün en aktif fırsatlarını gösterir.")
    if signals:
        df_sig = []
        for sym, sig in signals.items():
            strats = ", ".join([s.replace("[STRAT: ", "").replace("]", "") for s in sig.get("strategies", [])])
            df_sig.append({
                "Coin": sym,
                "Sinyal Frekansı": sig["count"],
                "Tetiklenen Stratejiler": strats
            })
        df = pd.DataFrame(df_sig).sort_values(by="Sinyal Frekansı", ascending=False)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Bugün henüz güçlü bir sinyal üretilmedi.")

with tab5:
    st.subheader("Sistem Motoru Canlı Logları")
    if logs:
        st.code("\n".join(reversed(logs[-30:])), language="text")
    else:
        st.info("Log kaydı bekleniyor...")
