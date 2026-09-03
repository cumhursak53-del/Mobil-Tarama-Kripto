import pandas as pd
import streamlit as st

from strategies.registry import all_strategies
from ui_common import setup_page, source_caption

data = setup_page("Strateji Lab", icon="🧪")
history = data.get("history") or []

st.title("Strateji Lab")
st.caption(source_caption(data))

st.markdown(
    """
### Bu sayfa ne yapar?
1. **Canli performans:** Kapanan islemlerden hangi strateji/kasa iyi gidiyor gosterir.
2. **Aday kurallar:** Patlama/Selale ve Rejim Osilator gibi birlesik kurallari listeler.
3. **Otomatik kesif (gelecek):** Webden strateji ogrenip tek basina guvenilir bot uretmek mumkun ama
   bugunku haliyle **henuz yok** — asagida neden ve nasil yapilabilecegi yaziyor.
"""
)

if history:
    df = pd.DataFrame(history)
    if "strategy" in df.columns and "pnl" in df.columns:
        g = df.groupby("strategy").agg(
            n=("pnl", "count"),
            toplam_pnl=("pnl", "sum"),
            ort_pnl=("pnl", "mean"),
            wr=("pnl", lambda s: (s > 0).mean()),
        ).sort_values("toplam_pnl", ascending=False)
        st.subheader("Canli test — strateji performansi")
        st.dataframe(g.reset_index(), use_container_width=True, hide_index=True)
    if "ledger" in df.columns and "pnl" in df.columns:
        gk = df.groupby("ledger").agg(
            n=("pnl", "count"),
            toplam_pnl=("pnl", "sum"),
            wr=("pnl", lambda s: (s > 0).mean()),
        ).sort_values("toplam_pnl", ascending=False)
        st.subheader("Kasa performansi")
        st.dataframe(gk.reset_index(), use_container_width=True, hide_index=True)
else:
    st.info("Henuz kapanan islem yok; performans tablosu bos.")

st.subheader("Kayitli strateji kasalari")
rows = [{"Kasa": s.ledger, "Sinif": s.__class__.__name__} for s in all_strategies()]
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=360)

st.subheader("Aday birlesik kurallar (manuel onayli)")
st.table({
    "Kural": [
        "Rejim + CCI/MACD + Stoch (RejimOsilator)",
        "MTF patlama/selale skoru >= 4 (PatlamaSelale)",
        "4H BOS + hacim + 1D yon",
        "BB squeeze + kirilim + retest",
    ],
    "Durum": ["Canli", "Canli", "Kismi (YapiKirilim kasasi)", "Kismi (BB_Squeeze kasasi)"],
    "Not": [
        "Oncelikli giris",
        "Ayri sayfada skor gorunur",
        "Ayri kasada",
        "Ayri kasada",
    ],
})

st.subheader("Otomatik strateji uretimi yapilir mi?")
st.markdown(
    """
**Kisa cevap:** Evet, ama tek tikla degil; asamali bir **Ar-Ge hattı** gerekir.

| Asama | Ne yapar | Zorluk |
|---|---|---|
| 1. Fikir havuzu | Web/PDF kaynaklarindan kural sablonlari (su an elle) | Orta |
| 2. Backtest | Gecmis veride WR, PF, max dusus olc | Kolay (motor var) |
| 3. Paper canli | Basarili adaylari ayri kasada dene | Kolay (su anki sistem) |
| 4. Otomatik secim | En iyi 2-3 kurali tut, kotuleri kapat | Orta |
| 5. Tam otonom AI | Internetten okuyup kodsuz strateji uret | Zor / guvenilmez |

**Neden hemen yapilmiyor?**
- Webden okunan stratejiler cogunlukla **overfit** veya **belirsiz** (ornek yok, stop yok).
- Kripto vadeli islemde kayma, likidasyon ve rejim degisimi backtesti yalanlar.
- Guvenilir bot icin: **net giris/cikis + risk + rejim filtresi + yeterli orneklem** sart.

**Sonraki mantikli adim:** Bu lab sayfasina bir **backtest calistir** butonu eklemek
(secilen coin listesi + mevcut stratejiler → en iyi 5'i paper'a al). Tam web taramasi icin
ayri bir arka plan isi (Render worker) gerekir.
"""
)

st.caption("Strateji Lab v1 — canli performans + yol haritasi. Otomatik web kesfi henuz aktif degil.")
