"""Krpito Live — PC masaustu izleme (VPS motor + Bybit verisi).

Tkinter ile calisir; ekstra paket gerekmez (requests + pandas zaten var).
VPS'teki motor JSON API'sinden veri ceker.
"""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)


def _apply_env() -> str:
    from engine.env_loader import load_live_env

    load_live_env(override=True)
    os.environ["KRPITO_REMOTE_ONLY"] = "1"
    os.environ["KRPITO_MODE"] = "live"
    from shared.ui_data import remote_live_url

    url = remote_live_url()
    os.environ["REMOTE_ENGINE_URL"] = url
    return url


DEFAULT_URL = _apply_env()

from shared.ui_data import (  # noqa: E402
    engine_status,
    history_rows,
    load_remote_live_data,
    pos_rows,
    signal_log_rows,
    signal_outcome_rows,
    signal_watch_rows,
)


REFRESH_MS = 30_000
MAX_TREE_ROWS = 300
SIG_LOG_MAX_SYMBOLS = 500


def _trim_signal_log(sig_log: dict | None, limit: int = SIG_LOG_MAX_SYMBOLS) -> dict:
    if not sig_log or limit <= 0:
        return sig_log or {}
    items = [
        (k, v)
        for k, v in sig_log.items()
        if not str(k).startswith("_") and isinstance(v, dict)
    ]
    if len(items) <= limit:
        return sig_log
    items.sort(key=lambda x: int(x[1].get("count") or 0), reverse=True)
    return dict(items[:limit])


class LiveMonitorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Krpito Canli — Hostinger + Bybit")
        self.root.geometry("1100x720")
        self.root.minsize(900, 560)
        self._refresh_job: str | None = None
        self._auto = tk.BooleanVar(value=True)
        self._loading = False

        self._build_toolbar()
        self._build_metrics()
        self._build_tabs()
        self._build_status()
        self.refresh()

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(fill=tk.X)

        ttk.Label(bar, text="VPS motor:").pack(side=tk.LEFT)
        self.url_var = tk.StringVar(value=DEFAULT_URL)
        ttk.Entry(bar, textvariable=self.url_var, width=48).pack(side=tk.LEFT, padx=(4, 8))
        ttk.Button(bar, text="Baglan", command=self._on_connect).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Yenile", command=self.refresh).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="Otomatik (30 sn)", variable=self._auto, command=self._toggle_auto).pack(
            side=tk.LEFT, padx=12
        )

    def _build_metrics(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Ozet", padding=8)
        frame.pack(fill=tk.X, padx=8, pady=(0, 4))

        labels = [
            ("Durum", "status"),
            ("Mod", "mode"),
            ("Ozsermaye", "equity"),
            ("Nakit", "cash"),
            ("Acik islem", "open"),
            ("Acik PnL", "unreal"),
            ("Kapanan PnL", "closed"),
            ("Guncelleme", "updated"),
        ]
        self.metric_vars: dict[str, tk.StringVar] = {}
        row = ttk.Frame(frame)
        row.pack(fill=tk.X)
        for i, (title, key) in enumerate(labels):
            col = ttk.Frame(row, padding=(0, 0, 16, 0))
            col.grid(row=0, column=i, sticky=tk.W)
            ttk.Label(col, text=title, font=("", 8)).pack(anchor=tk.W)
            var = tk.StringVar(value="-")
            self.metric_vars[key] = var
            ttk.Label(col, textvariable=var, font=("", 11, "bold")).pack(anchor=tk.W)

    def _build_tabs(self) -> None:
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.pos_tree = self._make_tree(nb, "Acik pozisyonlar")
        self.hist_tree = self._make_tree(nb, "Islem gecmisi")
        self.sig_tree = self._make_tree(nb, "Sinyal gunlugu")
        self.sig_analysis_tree = self._make_tree(nb, "Sinyal analizi (24s)")
        self.sig_watch_tree = self._make_tree(nb, "Aktif sinyal izleme")

        log_frame = ttk.Frame(nb)
        nb.add(log_frame, text="Motor log")
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=("Consolas", 10))
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _make_tree(self, parent: ttk.Notebook, title: str) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        parent.add(frame, text=title)
        tree = ttk.Treeview(frame, show="headings")
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    def _build_status(self) -> None:
        self.status_var = tk.StringVar(value="Hazir")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(
            fill=tk.X, padx=8, pady=(0, 6)
        )

    def _on_connect(self) -> None:
        url = self.url_var.get().strip().rstrip("/")
        if not url:
            messagebox.showwarning("URL", "Motor adresi bos olamaz.")
            return
        os.environ["REMOTE_ENGINE_URL"] = url
        self.refresh()

    def _toggle_auto(self) -> None:
        if self._auto.get():
            self._schedule_refresh()
        elif self._refresh_job:
            self.root.after_cancel(self._refresh_job)
            self._refresh_job = None

    def _schedule_refresh(self) -> None:
        if self._refresh_job:
            self.root.after_cancel(self._refresh_job)
        if self._auto.get():
            self._refresh_job = self.root.after(REFRESH_MS, self.refresh)

    def _fill_tree(self, tree: ttk.Treeview, df, *, max_rows: int | None = MAX_TREE_ROWS) -> None:
        tree.delete(*tree.get_children())
        if df is None or df.empty:
            tree["columns"] = ("mesaj",)
            tree.heading("mesaj", text="Veri")
            tree.column("mesaj", width=400)
            tree.insert("", tk.END, values=("Kayit yok",))
            return
        cols = list(df.columns)
        tree["columns"] = cols
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=max(80, min(160, len(c) * 10)), stretch=True)
        truncated = False
        if max_rows is not None and len(df) > max_rows:
            df = df.head(max_rows)
            truncated = True
        for row in df.itertuples(index=False, name=None):
            vals = [self._fmt(v) for v in row]
            tree.insert("", tk.END, values=vals)
        if truncated and max_rows is not None:
            tree.insert("", tk.END, values=(f"(Ilk {max_rows} satir)",) + ("",) * (len(cols) - 1))

    @staticmethod
    def _fmt(v) -> str:
        if v is None:
            return "-"
        if isinstance(v, (int, float)):
            from shared.price_format import format_price

            return format_price(float(v))
        return str(v)

    def refresh(self) -> None:
        if self._loading:
            return
        url = self.url_var.get().strip().rstrip("/")
        self._loading = True
        self.status_var.set(f"VPS'ten veri cekiliyor: {url}...")
        self.root.update_idletasks()

        def worker() -> None:
            err: Exception | None = None
            payload: dict | None = None
            try:
                data = load_remote_live_data(url)
                from shared.price_format import warm_tick_cache

                warm_tick_cache()
                payload = self._build_render_payload(data)
            except Exception as exc:
                err = exc
            self.root.after(0, lambda: self._on_refresh_done(payload, err, url))

        threading.Thread(target=worker, daemon=True).start()

    def _on_refresh_done(self, payload: dict | None, err: Exception | None, url: str) -> None:
        self._loading = False
        try:
            if err is not None:
                self.status_var.set(f"VPS ulasilamadi: {err}")
                self._render_error(str(err), url)
            else:
                self._apply_render(payload or {})
                source = (payload or {}).get("_source", url)
                self.status_var.set(f"Bagli — {source}")
        finally:
            self._schedule_refresh()

    def _render_error(self, msg: str, url: str) -> None:
        for key in self.metric_vars:
            self.metric_vars[key].set("-")
        self.metric_vars["status"].set("Baglanti yok")
        self.metric_vars["mode"].set("bybit (bekleniyor)")
        self._fill_tree(self.pos_tree, None)
        self._fill_tree(self.hist_tree, None)
        self._fill_tree(self.sig_tree, None)
        self._fill_tree(self.sig_analysis_tree, None)
        self._fill_tree(self.sig_watch_tree, None)
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(
            tk.END,
            f"VPS motoruna ulasilamadi.\n\nAdres: {url}\nHata: {msg}\n\n"
            "Kontrol:\n"
            "  1) Hostinger'da krpito-live calisiyor mu? (systemctl status krpito-live)\n"
            "  2) Firewall'da TCP 10001 acik mi?\n"
            "  3) live.env icinde REMOTE_ENGINE_URL=http://76.13.150.125:10001\n",
        )

    def _build_render_payload(self, data: dict) -> dict:
        import pandas as pd

        live = bool(data.get("live_exchange"))
        active = data.get("active_positions") or {}
        if not live:
            active = {}
        history = data.get("history") or []
        cash = float(data.get("balance") or 0)
        equity = float(data.get("equity") or cash)
        if not live:
            equity = cash
        unreal = 0.0 if not live else sum(
            float(p.get("unrealized_pnl") or 0) for p in active.values() if isinstance(p, dict)
        )
        closed = float(data.get("closed_pnl_total") or 0)
        if closed == 0 and history:
            closed = sum(float(h.get("pnl") or 0) for h in history if isinstance(h, dict))

        label, _kind, detail = engine_status(data)
        mode = str(data.get("trading_mode") or "-")
        exchange = "Bybit emir ACIK" if live else "Tarama only (emir yok)"
        kasa = data.get("live_combo_ledger") or "-"
        flags = data.get("engine_flags") or {}
        sig_log = _trim_signal_log(data.get("signal_log") or {})
        if not flags.get("signal_analysis") and "signal_watchlist" not in data:
            sig_analysis_df = pd.DataFrame(
                [{"mesaj": "VPS guncel degil — Hostinger terminalde git pull + deploy_vps.sh calistirin"}]
            )
            sig_watch_df = None
        else:
            sig_analysis_df = signal_outcome_rows(data.get("signal_outcome_log") or [])
            sig_watch_df = signal_watch_rows(data.get("signal_watchlist") or [])

        return {
            "_source": data.get("_source"),
            "metrics": {
                "status": label,
                "mode": f"{mode} | {exchange} | {kasa}",
                "equity": f"${equity:,.2f}",
                "cash": f"${cash:,.2f}",
                "open": "0" if not live else str(len(active)),
                "unreal": "$+0.00" if not live else f"${unreal:+,.2f}",
                "closed": f"${closed:+,.2f}",
                "updated": str(data.get("updated_at") or "-"),
            },
            "pos_df": pos_rows(active),
            "hist_df": history_rows(history),
            "sig_df": signal_log_rows(sig_log),
            "sig_analysis_df": sig_analysis_df,
            "sig_watch_df": sig_watch_df,
            "logs": data.get("engine_logs") or [],
            "detail": detail,
        }

    def _apply_render(self, payload: dict) -> None:
        metrics = payload.get("metrics") or {}
        for key, val in metrics.items():
            if key in self.metric_vars:
                self.metric_vars[key].set(str(val))

        self._fill_tree(self.pos_tree, payload.get("pos_df"))
        self._fill_tree(self.hist_tree, payload.get("hist_df"))
        self._fill_tree(self.sig_tree, payload.get("sig_df"))
        self._fill_tree(self.sig_analysis_tree, payload.get("sig_analysis_df"), max_rows=None)
        self._fill_tree(self.sig_watch_tree, payload.get("sig_watch_df"), max_rows=None)

        logs = payload.get("logs") or []
        detail = payload.get("detail") or ""
        self.log_text.delete("1.0", tk.END)
        if logs:
            self.log_text.insert(tk.END, "\n".join(str(x) for x in logs))
            self.log_text.see(tk.END)
        else:
            self.log_text.insert(tk.END, f"Log yok. ({detail})")


def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    LiveMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
