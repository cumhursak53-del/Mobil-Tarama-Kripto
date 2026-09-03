import pandas as pd
import streamlit as st

from strategies.registry import all_strategies, lab_strategies
from ui_common import load_lab_data, setup_page, source_caption

data = setup_page("Strateji Lab", icon="🧪")
history = data.get("history") or []
lab_candidates = data.get("lab_candidates") or []

st.title("Strateji Lab")
st.caption(source_caption(data))
st.info("Strateji **uretim hattinin canli durumu** icin sol menuden **Strateji Uretimi** sayfasina gec.")

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

st.subheader("Lab aday kasalari (paper)")
if lab_candidates:
    rows = []
    for c in lab_candidates:
        m = c.get("metrics") or {}
        bt = c.get("backtest") or {}
        rows.append({
            "Kasa": c.get("ledger"),
            "Tarif": c.get("recipe_id"),
            "Paper baslangic": c.get("paper_started_at"),
            "Islem": m.get("n", 0),
            "WR": f"{100 * float(m.get('wr') or 0):.0f}%",
            "PnL": f"${float(m.get('pnl') or 0):+.2f}",
            "BT islem": bt.get("n", "-"),
            "BT PF": bt.get("profit_factor", "-"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("Henuz lab adayi yok. Asagidaki komutlarla uretilebilir.")

lab_local = load_lab_data(force_version=st.session_state.get("refresh_version", 0))
backtests = lab_local.get("backtests") or []
if backtests:
    st.subheader("Son backtest sonuclari")
    bt_rows = []
    for b in backtests[-30:]:
        m = b.get("metrics") or {}
        bt_rows.append({
            "Tarif": b.get("recipe_id"),
            "Islem": m.get("n"),
            "WR": f"{100 * float(m.get('win_rate') or 0):.0f}%",
            "PF": m.get("profit_factor"),
            "PnL": m.get("pnl"),
            "Gecti": "Evet" if m.get("passed") else "Hayir",
        })
    st.dataframe(pd.DataFrame(bt_rows), use_container_width=True, hide_index=True)

st.subheader("Kayitli strateji kasalari (30 sabit + lab)")
rows = [{"Kasa": s.ledger, "Sinif": s.__class__.__name__} for s in all_strategies()]
lab_only = lab_strategies(lab_local) if lab_local else []
for s in lab_only:
    if not any(r["Kasa"] == s.ledger for r in rows):
        rows.append({"Kasa": s.ledger, "Sinif": s.__class__.__name__})
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=360)

st.subheader("Komutlar (istege bagli — lokal gelistirme)")
st.code(
    """python -m engine.main lab-generate --limit 40
python -m engine.main lab-backtest --limit 20 --universe 6""",
    language="bash",
)
st.caption("Render'da Shell gerekmez; motor otomasyonu kendisi calistirir.")

st.caption("Strateji Lab — performans analizi. Uretim durumu: **Strateji Uretimi** sayfasi.")
