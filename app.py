import streamlit as st
import pandas as pd
import json
import os
import requests

st.set_page_config(page_title="Kurumsal MTF Bot", page_icon="🤖", layout="wide")

@st.cache_data(ttl=5)
def fetch_data():
    try:
        res = requests.get("https://mobil-tarama-kripto.onrender.com", timeout=3)
        if res.status_code == 200:
            return res.json()
    except:
        pass
        
    try:
        res = requests.get("http://127.0.0.1:10000", timeout=2)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    
    try:
        headers = {
            "Authorization": "token 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", 
            "Accept": "application/vnd.github.v3.raw"
        }
        res = requests.get("https://api.github.com/repos/cumhursak53-del/Mobil-Tarama-Krypto/contents/durum.json?ref=main", headers=headers, timeout=5)
        if res.status_code == 200:
            return json.loads(res.text)
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
    st.warning("📡 Canlı sunucuya veya GitHub'a bağlanılıyor, lütfen 10 saniye sonra sayfayı yenileyin...")
    st.stop()

ledgers = data.get("ledgers", {})
active_pos = data.get("active_positions", {})
history = data.get("history", [])
signals = data.get("signal_log", {})
logs = data.get("engine_logs", [])

st.title("🤖 Kurumsal Kripto Fon Yönetimi")

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
    st.subheader("Açık Pozisyonlar ve Anlık Kâr/Zarar Takibi")
    if active_pos:
        df_active = []
        for sym, pos in active_pos.items():
            entry = pos['entry_price']
            curr = pos.get('current_price', entry)
            side = pos['side']
            margin = pos['margin']
            leverage = 10
            
            ratio = (curr - entry) / entry if side == "BUY" else (entry - curr) / entry
            roe_pct = ratio * leverage * 100
            pnl_usd = margin * leverage * ratio
            
            target_roe = 10.0
            if side == "BUY":
                target_price = entry * (1 + (target_roe / (100 * leverage)))
            else:
                target_price = entry * (1 - (target_roe / (100 * leverage)))

            df_active.append({
                "Coin": sym,
                "Yön": "🟩 LONG" if side == "BUY" else "🟥 SHORT",
                "Kasa": pos.get("ledger_name", "-").replace("Kasa_", "").replace("_", " "),
                "Strateji": pos.get("strategy", "-").replace("[STRAT: ", "").replace("]", ""),
                "Marjin": f"${margin:.2f}",
                "Giriş Fiyatı": f"${entry:.4f}",
                "Hedef (Trailing Başlangıcı)": f"${target_price:.4f}",
                "Anlık Fiyat": f"${curr:.4f}",
                "Anlık ROE (%)": f"%{roe_pct:.2f}",
                "Anlık PnL ($)": f"${pnl_usd:.2f}",
                "MFE (Zirve Kâr)": f"${pos.get('max_reached_price', entry):.4f}",
                "MAE (Dip Zarar)": f"${pos.get('min_reached_price', entry):.4f}"
            })
            
        df = pd.DataFrame(df_active)
        
        def color_active_pnl(val):
            try:
                val_float = float(val.replace('$', '').replace('%', ''))
                color = '#00FF00' if val_float > 0 else ('#FF0000' if val_float < 0 else 'white')
            except:
                color = 'white'
            return f'color: {color}'
            
        st.dataframe(df.style.map(color_active_pnl, subset=['Anlık ROE (%)', 'Anlık PnL ($)']), use_container_width=True)
    else:
        st.success("Şu an açık pozisyon bulunmuyor. Sistem pusu modunda.")

with tab3:
    st.subheader("Kapanmış İşlemler (Kâr/Zarar ve Fiyat Sınırları Analizi)")
    if history:
        df_hist = []
        for h in reversed(history[-50:]): 
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
