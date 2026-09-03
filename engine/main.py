from __future__ import annotations

import argparse
import json

from engine.backtest import backtest_symbol, summarize
from engine.data import fetch_all_timeframes, fetch_dominance, fetch_symbols
from engine.lab_state import load_lab_state
from engine.paper import run_paper, run_scan
from engine.portfolio import Portfolio
from strategies.registry import all_strategies


def cmd_validate() -> None:
    from tests.test_indicators import run_all
    run_all()


def cmd_paper(n: int) -> None:
    run_paper(n)


def cmd_scan_once(n: int) -> None:
    pf = Portfolio()
    symbols = fetch_symbols(n)
    run_scan(pf, symbols, fetch_dominance())
    print(json.dumps({"positions": len(pf.positions), "equity": pf.snapshot()["equity"]}, indent=2))


def cmd_backtest(symbols: list[str], n_universe: int) -> None:
    if not symbols:
        symbols = fetch_symbols(n_universe)[:10]
    dominance = fetch_dominance()
    results = []
    for sym in symbols:
        print(f"Backtest {sym} ...", flush=True)
        frames = fetch_all_timeframes(sym)
        results.append(backtest_symbol(sym, frames, dominance))
    table = summarize(results)
    print(table.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    n_strats = len(all_strategies())
    print(f"\nStrateji sayisi: {n_strats} | Sembol: {', '.join(symbols)}")


def cmd_lab_generate(limit: int) -> None:
    from engine.lab_runner import run_lab_pipeline
    from engine.lab_state import load_lab_state

    run_lab_pipeline(force=True)
    state = load_lab_state()
    print(json.dumps({"total_recipes": len(state.get("recipes") or [])}, indent=2))


def cmd_lab_backtest(limit: int, symbols: list[str], n_universe: int) -> None:
    from engine.lab_runner import run_lab_pipeline
    from engine.lab_state import load_lab_state

    result = run_lab_pipeline(force=True)
    state = load_lab_state()
    print(json.dumps({**result, "backtest_count": len(state.get("backtests") or [])}, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="PDF MTF trading engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="Yerel gosterge dogrulama")
    paper = sub.add_parser("paper", help="Canli paper (mum kapanisi)")
    paper.add_argument("--symbols", type=int, default=0, help="0 = tum piyasa")
    once = sub.add_parser("scan", help="Tek tarama dongusu")
    once.add_argument("--symbols", type=int, default=40)
    bt = sub.add_parser("backtest", help="Kapali mum walk-forward")
    bt.add_argument("--symbol", action="append", default=[])
    bt.add_argument("--universe", type=int, default=8)

    gen = sub.add_parser("lab-generate", help="Kombinator ile tarif uret")
    gen.add_argument("--limit", type=int, default=40)
    lab = sub.add_parser("lab-backtest", help="Lab tariflerini backtest et ve aday sec")
    lab.add_argument("--limit", type=int, default=20)
    lab.add_argument("--symbol", action="append", default=[])
    lab.add_argument("--universe", type=int, default=6)

    args = p.parse_args()
    if args.cmd == "validate":
        cmd_validate()
    elif args.cmd == "paper":
        cmd_paper(args.symbols)
    elif args.cmd == "scan":
        cmd_scan_once(args.symbols)
    elif args.cmd == "backtest":
        cmd_backtest(args.symbol, args.universe)
    elif args.cmd == "lab-generate":
        cmd_lab_generate(args.limit)
    elif args.cmd == "lab-backtest":
        cmd_lab_backtest(args.limit, args.symbol, args.universe)


if __name__ == "__main__":
    main()
