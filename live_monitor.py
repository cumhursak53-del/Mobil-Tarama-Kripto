"""Krpito Live — PC masaustu izleme (VPS motor + Bybit verisi).

Tkinter ile calisir; ekstra paket gerekmez (requests + pandas zaten var).
VPS'teki motor JSON API'sinden veri ceker.
"""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

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
    build_excel_bytes,
    engine_status,
    history_rows,
    load_remote_live_data,
    pos_rows,
    signal_log_rows,
    signal_outcome_rows,
    signal_watch_rows,
    market_commentary_rows,
    strategy_result_tables,
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
        self._exporting = False
        self._last_export_data: dict | None = None

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
        ttk.Button(bar, text="Excel rapor", command=self._export_excel).pack(side=tk.LEFT, padx=2)
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
        self._build_commentary_tab(nb)
        self._build_strategy_tab(nb)

        log_frame = ttk.Frame(nb)
        nb.add(log_frame, text="Motor log")
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=("Consolas", 10))
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_commentary_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Piyasa yorumu")
        bar = ttk.Frame(frame, padding=(4, 4))
        bar.pack(fill=tk.X)
        self._commentary_caption = tk.StringVar(value="Yorum gecmisi yuklenmedi")
        ttk.Label(bar, textvariable=self._commentary_caption).pack(side=tk.LEFT)
        paned = ttk.Panedwindow(frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        top = ttk.LabelFrame(paned, text="Tur yorumlari — satira tiklayinca tam metin")
        bottom = ttk.LabelFrame(paned, text="Secili yorum")
        paned.add(top, weight=1)
        paned.add(bottom, weight=2)
        self.commentary_tree = self._tree_in(top)
        self.commentary_tree.bind("<<TreeviewSelect>>", self._on_commentary_select)
        self._commentary_text = tk.Text(bottom, wrap=tk.WORD, font=("", 10))
        scroll = ttk.Scrollbar(bottom, command=self._commentary_text.yview)
        self._commentary_text.configure(yscrollcommand=scroll.set)
        self._commentary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._commentary_text.insert(
            tk.END,
            "Her tarama turu bitince Bitcoin, hakimiyet ve altcoin evrelerine gore yorum burada listelenir.\n"
            "VPS guncel degilse bu liste bos kalir — Hostinger'da git pull + deploy_vps.sh calistirin.",
        )
        self._commentary_text.configure(state=tk.DISABLED)
        self._commentary_entries: list[dict] = []

    def _on_commentary_select(self, _event=None) -> None:
        sel = self.commentary_tree.selection()
        if not sel:
            return
        idx = self.commentary_tree.index(sel[0])
        if idx < 0 or idx >= len(self._commentary_entries):
            return
        text = str(self._commentary_entries[idx].get("Yorum") or "")
        self._commentary_text.configure(state=tk.NORMAL)
        self._commentary_text.delete("1.0", tk.END)
        self._commentary_text.insert(tk.END, text)
        self._commentary_text.configure(state=tk.DISABLED)

    def _build_strategy_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Strateji sonuclari")
        bar = ttk.Frame(frame, padding=(4, 4))
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Strateji:").pack(side=tk.LEFT)
        self._strategy_filter = tk.StringVar(value="Tumu")
        self._strategy_combo = ttk.Combobox(
            bar, textvariable=self._strategy_filter, state="readonly", width=42
        )
        self._strategy_combo.pack(side=tk.LEFT, padx=(4, 12))
        self._strategy_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_strategy_detail())
        self._strategy_caption = tk.StringVar(value="Ozet yuklenmedi")
        ttk.Label(bar, textvariable=self._strategy_caption).pack(side=tk.LEFT)
        paned = ttk.Panedwindow(frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        top = ttk.LabelFrame(paned, text="Strateji ozeti — satira tiklayinca detay filtrelenir")
        bottom = ttk.LabelFrame(paned, text="Sinyal detayi (biten + devam)")
        paned.add(top, weight=1)
        paned.add(bottom, weight=2)
        self.strategy_sum_tree = self._tree_in(top)
        self.strategy_detail_tree = self._tree_in(bottom)
        self.strategy_sum_tree.bind("<<TreeviewSelect>>", self._on_strategy_summary_select)
        self._strategy_detail_df = None

    def _tree_in(self, parent: ttk.Frame) -> ttk.Treeview:
        holder = ttk.Frame(parent)
        holder.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(holder, show="headings")
        vsb = ttk.Scrollbar(holder, orient=tk.VERTICAL, command=tree.yview)
        hsb = ttk.Scrollbar(holder, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        return tree

    def _on_strategy_summary_select(self, _event=None) -> None:
        sel = self.strategy_sum_tree.selection()
        if not sel:
            return
        values = self.strategy_sum_tree.item(sel[0], "values")
        if not values:
            return
        name = str(values[0])
        if name and name != "Kayit yok":
            self._strategy_filter.set(name)
            self._apply_strategy_detail()

    def _apply_strategy_detail(self) -> None:
        df = self._strategy_detail_df
        chosen = self._strategy_filter.get().strip() or "Tumu"
        if df is None or getattr(df, "empty", True):
            self._fill_tree(self.strategy_detail_tree, None, max_rows=None)
            return
        view = df if chosen == "Tumu" else df[df["Strateji"] == chosen]
        self._fill_tree(self.strategy_detail_tree, view, max_rows=None)

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
        if v is None or isinstance(v, bool):
            return "-" if v is None else ("Evet" if v else "Hayir")
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
            raw_data: dict | None = None
            try:
                data = load_remote_live_data(url, timeout=30)
                raw_data = data
                payload = self._build_render_payload(data)
            except Exception as exc:
                err = exc
            self.root.after(0, lambda: self._on_refresh_done(payload, err, url, raw_data))

        threading.Thread(target=worker, daemon=True).start()

    def _on_refresh_done(
        self,
        payload: dict | None,
        err: Exception | None,
        url: str,
        raw_data: dict | None = None,
    ) -> None:
        self._loading = False
        try:
            if err is not None:
                self._last_export_data = None
                self.status_var.set(f"VPS ulasilamadi: {err}")
                self._render_error(str(err), url)
            else:
                self._last_export_data = raw_data
                self._apply_render(payload or {})
                source = (payload or {}).get("_source", url)
                n_an = (payload or {}).get("analysis_count", 0)
                n_iz = (payload or {}).get("watch_count", 0)
                self.status_var.set(f"Bagli — {source} | sinyal analizi {n_an} | aktif izleme {n_iz}")
        finally:
            self._schedule_refresh()

    def _export_excel(self) -> None:
        if self._exporting:
            return
        if not self._last_export_data:
            messagebox.showwarning("Excel", "Once VPS'ten veri yukleyin (Baglan / Yenile).")
            return
        default_name = f"krpito_canli_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        path = filedialog.asksaveasfilename(
            title="Excel rapor kaydet",
            defaultextension=".xlsx",
            filetypes=[("Excel dosyasi", "*.xlsx")],
            initialfile=default_name,
        )
        if not path:
            return
        export_data = self._last_export_data
        self._exporting = True
        self.status_var.set("Excel rapor hazirlaniyor...")

        def worker() -> None:
            err: Exception | None = None
            try:
                xlsx = build_excel_bytes(export_data)
                with open(path, "wb") as f:
                    f.write(xlsx)
            except Exception as exc:
                err = exc
            self.root.after(0, lambda: self._on_export_done(path, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_export_done(self, path: str, err: Exception | None) -> None:
        self._exporting = False
        if err is not None:
            messagebox.showerror("Excel", f"Rapor olusturulamadi:\n{err}")
            self.status_var.set(f"Excel hatasi: {err}")
            return
        messagebox.showinfo("Excel", f"Rapor kaydedildi:\n{path}")
        self.status_var.set(f"Excel kaydedildi — {os.path.basename(path)}")

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
        self._strategy_detail_df = None
        self._fill_tree(self.strategy_sum_tree, None, max_rows=None)
        self._fill_tree(self.strategy_detail_tree, None, max_rows=None)
        self._fill_tree(self.commentary_tree, None, max_rows=None)
        self._commentary_entries = []
        self._commentary_caption.set("Yorum alinamadi")
        self._commentary_text.configure(state=tk.NORMAL)
        self._commentary_text.delete("1.0", tk.END)
        self._commentary_text.insert(tk.END, "VPS baglantisi yok.")
        self._commentary_text.configure(state=tk.DISABLED)
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
        strategy_sum_df = None
        strategy_detail_df = None
        if not flags.get("signal_analysis") and "signal_watchlist" not in data:
            sig_analysis_df = pd.DataFrame(
                [{"mesaj": "VPS guncel degil — Hostinger terminalde git pull + deploy_vps.sh calistirin"}]
            )
            sig_watch_df = None
        else:
            sig_analysis_df = signal_outcome_rows(data.get("signal_outcome_log") or [])
            sig_watch_df = signal_watch_rows(data.get("signal_watchlist") or [])
            strategy_sum_df, strategy_detail_df = strategy_result_tables(
                data.get("signal_outcome_log") or [],
                data.get("signal_watchlist") or [],
            )
        if data.get("market_commentary_log") is None and "signal_watchlist" in data:
            commentary_df = pd.DataFrame([{
                "Bilgi": "VPS guncel degil — piyasa yorumu yok. Hostinger'da git pull + deploy_vps.sh calistirin.",
            }])
        else:
            commentary_df = market_commentary_rows(data.get("market_commentary_log") or [])

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
            "strategy_sum_df": strategy_sum_df,
            "strategy_detail_df": strategy_detail_df,
            "commentary_df": commentary_df,
            "analysis_count": 0 if sig_analysis_df is None or sig_analysis_df.empty else len(sig_analysis_df),
            "watch_count": 0 if sig_watch_df is None or getattr(sig_watch_df, "empty", True) else len(sig_watch_df),
            "logs": data.get("engine_logs") or [],
            "detail": detail,
        }

    def _apply_render(self, payload: dict) -> None:
        metrics = payload.get("metrics") or {}
        for key, val in metrics.items():
            if key in self.metric_vars:
                self.metric_vars[key].set(str(val))

        logs = payload.get("logs") or []
        detail = payload.get("detail") or ""
        self.log_text.delete("1.0", tk.END)
        if logs:
            self.log_text.insert(tk.END, "\n".join(str(x) for x in logs))
            self.log_text.see(tk.END)
        else:
            self.log_text.insert(tk.END, f"Log yok. ({detail})")

        for tree, df, limit in (
            (self.pos_tree, payload.get("pos_df"), MAX_TREE_ROWS),
            (self.hist_tree, payload.get("hist_df"), MAX_TREE_ROWS),
            (self.sig_tree, payload.get("sig_df"), MAX_TREE_ROWS),
            (self.sig_analysis_tree, payload.get("sig_analysis_df"), None),
            (self.sig_watch_tree, payload.get("sig_watch_df"), None),
            (self.commentary_tree, payload.get("commentary_df"), None),
        ):
            try:
                self._fill_tree(tree, df, max_rows=limit)
            except Exception as exc:
                self.log_text.insert(tk.END, f"\nTablo hatasi: {exc}\n")
        self._show_strategy_results(payload.get("strategy_sum_df"), payload.get("strategy_detail_df"))
        self._show_commentary(payload.get("commentary_df"))

    def _show_commentary(self, df) -> None:
        entries: list[dict] = []
        if df is not None and not getattr(df, "empty", True):
            if "Bilgi" in df.columns:
                self._commentary_caption.set(str(df.iloc[0].get("Bilgi") or "Yorum yok"))
                self._commentary_entries = []
                self._commentary_text.configure(state=tk.NORMAL)
                self._commentary_text.delete("1.0", tk.END)
                self._commentary_text.insert(tk.END, str(df.iloc[0].get("Bilgi") or ""))
                self._commentary_text.configure(state=tk.DISABLED)
                return
            entries = df.to_dict("records")
        self._commentary_entries = entries
        n = len(entries)
        self._commentary_caption.set(f"{n} tur yorumu" if n else "Henuz tur yorumu yok")
        if n:
            self.commentary_tree.selection_set(self.commentary_tree.get_children()[0])
            self._on_commentary_select()

    def _show_strategy_results(self, summary, detail) -> None:
        self._strategy_detail_df = detail
        try:
            self._fill_tree(self.strategy_sum_tree, summary, max_rows=None)
        except Exception as exc:
            self.log_text.insert(tk.END, f"\nStrateji ozet hatasi: {exc}\n")
        names = ["Tumu"]
        if summary is not None and not getattr(summary, "empty", True) and "Strateji" in summary.columns:
            names.extend(str(x) for x in summary["Strateji"].tolist())
        current = self._strategy_filter.get()
        self._strategy_combo["values"] = names
        if current not in names:
            self._strategy_filter.set("Tumu")
        biten = devam = 0
        if detail is not None and not getattr(detail, "empty", True):
            biten = int((detail["Durum"] == "Biten").sum())
            devam = int((detail["Durum"] == "Devam").sum())
        self._strategy_caption.set(f"{len(names) - 1} strateji | biten {biten} | devam {devam}")
        self._apply_strategy_detail()


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
