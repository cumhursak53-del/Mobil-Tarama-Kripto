"""Krpito MTF — Streamlit ana giris noktasi."""
import streamlit as st

from ui_common import render_global_sidebar, run_autorefresh

st.set_page_config(
    page_title="Krpito MTF",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_global_sidebar()
run_autorefresh()

pg = st.navigation(
    [
        st.Page("screens/home.py", title="Ana ekran", icon="📈", default=True),
        st.Page("screens/patlama_selale.py", title="Patlama Selale", icon="🚀"),
        st.Page("screens/strateji_lab.py", title="Strateji Lab", icon="🧪"),
        st.Page("screens/strateji_uretimi.py", title="Strateji Uretimi", icon="⚙️"),
    ],
    position="top",
)
pg.run()
