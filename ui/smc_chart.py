"""SMC grafik — Plotly mum + zone overlay + yapı etiketleri + HTF panel."""
from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from structure.smc import DealingRange, OrderBlock, SMCAnalysis
from structure.smc_labels import structure_chart_labels


def _add_hline(fig: go.Figure, y: float, *, color: str, dash: str, label: str, x0, x1, row: int = 1, col: int = 1) -> None:
    fig.add_shape(
        type="line", x0=x0, x1=x1, y0=y, y1=y,
        line=dict(color=color, width=1, dash=dash),
        row=row, col=col,
    )
    fig.add_annotation(
        x=x1, y=y, text=label, showarrow=False, xanchor="left",
        font=dict(size=9, color=color), row=row, col=col,
    )


def _add_rect(
    fig: go.Figure, x0, x1, y0, y1, *,
    fillcolor: str, line_color: str, label: str = "",
    row: int = 1, col: int = 1,
) -> None:
    fig.add_shape(
        type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
        fillcolor=fillcolor, line=dict(color=line_color, width=1),
        layer="below", row=row, col=col,
    )
    if label:
        fig.add_annotation(
            x=x0, y=max(y0, y1), text=label, showarrow=False,
            xanchor="left", yanchor="bottom", font=dict(size=8, color=line_color),
            row=row, col=col,
        )


def _overlay_zones(
    fig: go.Figure,
    df: pd.DataFrame,
    sl: pd.DataFrame,
    analysis: SMCAnalysis,
    *,
    x0, x1,
    row: int = 1,
) -> None:
    dr: Optional[DealingRange] = analysis.dealing_range
    if dr:
        _add_hline(fig, dr.high, color="#888", dash="dot", label="DR-H", x0=x0, x1=x1, row=row)
        _add_hline(fig, dr.low, color="#888", dash="dot", label="DR-L", x0=x0, x1=x1, row=row)
        _add_hline(fig, dr.equilibrium, color="#aaa", dash="dash", label="EQ", x0=x0, x1=x1, row=row)
        _add_rect(fig, x0, x1, dr.ote_low, dr.ote_high, fillcolor="rgba(100,149,237,0.14)", line_color="#6495ed", label="OTE", row=row)
        _add_rect(fig, x0, x1, dr.low, dr.equilibrium, fillcolor="rgba(0,180,100,0.07)", line_color="rgba(0,180,100,0.45)", row=row)
        _add_rect(fig, x0, x1, dr.equilibrium, dr.high, fillcolor="rgba(220,80,80,0.07)", line_color="rgba(220,80,80,0.45)", row=row)

    for lv in analysis.eql_levels[-3:]:
        _add_hline(fig, lv, color="#00bcd4", dash="dot", label="EQL", x0=x0, x1=x1, row=row)
    for lv in analysis.eqh_levels[-3:]:
        _add_hline(fig, lv, color="#ff9800", dash="dot", label="EQH", x0=x0, x1=x1, row=row)

    for pool in analysis.liquidity_pools[-6:]:
        if pool.swept:
            col = "#00e676" if pool.side == "buy" else "#ff5252"
            _add_hline(fig, pool.level, color=col, dash="solid", label=f"LQ{pool.touches}", x0=x0, x1=x1, row=row)

    ob_index = df.iloc[-80:] if len(df) > 80 else df

    def _plot_block(ob: OrderBlock, *, fill: str, border: str, label: str) -> None:
        if ob.mitigated:
            return
        rel = min(ob.bar_index, len(ob_index) - 1)
        bx0 = ob_index.index[rel]
        lo, hi = min(ob.bottom, ob.top), max(ob.bottom, ob.top)
        _add_rect(fig, bx0, x1, lo, hi, fillcolor=fill, line_color=border, label=label, row=row)

    for ob in analysis.order_blocks:
        if ob.block_type != "order":
            continue
        if ob.structure == "internal":
            fill = "rgba(0,200,120,0.10)" if ob.side == "bull" else "rgba(255,82,82,0.10)"
            border = "#66bb6a" if ob.side == "bull" else "#ef5350"
            tag = "iOB↑" if ob.side == "bull" else "iOB↓"
        else:
            fill = "rgba(0,200,120,0.22)" if ob.side == "bull" else "rgba(255,82,82,0.22)"
            border = "#00c853" if ob.side == "bull" else "#ff5252"
            tag = "OB↑" if ob.side == "bull" else "OB↓"
        if ob.side == "bull":
            _plot_block(ob, fill=fill, border=border, label=tag)
        else:
            _plot_block(ob, fill=fill, border=border, label=tag)

    for ob in analysis.breaker_blocks:
        if ob.side == "bull":
            _plot_block(ob, fill="rgba(33,150,243,0.22)", border="#2196f3", label="BRK↑")
        else:
            _plot_block(ob, fill="rgba(156,39,176,0.22)", border="#9c27b0", label="BRK↓")

    for fvg in sorted([f for f in analysis.fvgs if not f.mitigated], key=lambda f: f.priority, reverse=True)[:4]:
        lo, hi = min(fvg.bottom, fvg.top), max(fvg.bottom, fvg.top)
        rel = min(fvg.bar_index, len(ob_index) - 1)
        fx0 = ob_index.index[rel]
        tag = "IFVG" if fvg.is_inversion else "FVG"
        col = "#ffeb3b" if fvg.side == "bull" else "#ce93d8"
        fill = "rgba(255,235,59,0.18)" if fvg.side == "bull" else "rgba(206,147,216,0.18)"
        _add_rect(fig, fx0, x1, lo, hi, fillcolor=fill, line_color=col, label=tag, row=row)
        if fvg.ce_level:
            _add_hline(fig, fvg.ce_level, color=col, dash="dashdot", label="CE", x0=fx0, x1=x1, row=row)


def build_smc_chart(
    df: pd.DataFrame,
    analysis: SMCAnalysis,
    *,
    title: str = "",
    lookback: int = 120,
    htf_df: Optional[pd.DataFrame] = None,
    htf_analysis: Optional[SMCAnalysis] = None,
) -> go.Figure:
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title=title or "Veri yok")
        return fig

    has_htf = htf_df is not None and not htf_df.empty and htf_analysis is not None
    rows = 2 if has_htf else 1
    row_heights = [0.32, 0.68] if has_htf else [1.0]

    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=row_heights,
        subplot_titles=(["4H HTF bias", title.split("|")[0].strip()] if has_htf else [title]),
    )

    sl = df.iloc[-lookback:].copy()
    x0, x1 = sl.index[0], sl.index[-1]
    main_row = 2 if has_htf else 1

    fig.add_trace(
        go.Candlestick(
            x=sl.index, open=sl["open"], high=sl["high"], low=sl["low"], close=sl["close"],
            name="LTF", increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        ),
        row=main_row, col=1,
    )

    if has_htf:
        hsl = htf_df.iloc[-60:].copy()
        hx0, hx1 = hsl.index[0], hsl.index[-1]
        fig.add_trace(
            go.Candlestick(
                x=hsl.index, open=hsl["open"], high=hsl["high"], low=hsl["low"], close=hsl["close"],
                name="4H", increasing_line_color="#42a5f5", decreasing_line_color="#ef5350",
            ),
            row=1, col=1,
        )
        _overlay_zones(fig, htf_df, hsl, htf_analysis, x0=hx0, x1=hx1, row=1)
        fig.add_annotation(
            x=hx1, y=float(hsl["close"].iloc[-1]), xref="x", yref="y",
            text=f"HTF {htf_analysis.trend} | {htf_analysis.external_event}",
            showarrow=False, xanchor="right", font=dict(size=10, color="#90caf9"),
            row=1, col=1,
        )

    _overlay_zones(fig, df, sl, analysis, x0=x0, x1=x1, row=main_row)

    labels = structure_chart_labels(
        df, analysis,
        internal_n=analysis.internal_swing_n,
        external_n=analysis.external_swing_n,
        lookback=lookback,
    )
    if labels:
        fig.add_trace(
            go.Scatter(
                x=[lb.x for lb in labels],
                y=[lb.y for lb in labels],
                mode="markers+text",
                text=[lb.text for lb in labels],
                textposition="top center",
                marker=dict(
                    size=[lb.size for lb in labels],
                    symbol=[lb.symbol for lb in labels],
                    color=[lb.color for lb in labels],
                    line=dict(width=1, color="#111"),
                ),
                name="Yapi",
                hoverinfo="skip",
            ),
            row=main_row, col=1,
        )

    price = float(sl["close"].iloc[-1])
    badge = (
        f"Grade L:{analysis.setup_grade_long} S:{analysis.setup_grade_short} | "
        f"Conf {analysis.confluence_long}/{analysis.confluence_short} | "
        f"Swings int/ext {analysis.internal_swing_n}/{analysis.external_swing_n}"
    )
    if analysis.killzone:
        badge += f" | KZ:{analysis.session}"

    fig.add_annotation(
        x=x1, y=price, text=f"{price:.4g}", showarrow=True, arrowhead=2, ax=-40, ay=0,
        font=dict(size=11), row=main_row, col=1,
    )
    fig.update_layout(
        title=badge if not has_htf else title,
        xaxis_rangeslider_visible=False,
        height=680 if has_htf else 580,
        margin=dict(l=40, r=40, t=60, b=40),
        template="plotly_dark",
        showlegend=False,
    )
    fig.update_xaxes(type="date", row=main_row, col=1)
    if has_htf:
        fig.update_xaxes(type="date", row=1, col=1)
    return fig
