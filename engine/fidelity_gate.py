"""Paper/backtest kabul kapilari — walk-forward ve canli performans."""
from __future__ import annotations

from engine.config import (
    FIDELITY_MAX_DD,
    FIDELITY_MIN_BACKTEST_DAYS,
    FIDELITY_MIN_PF,
    FIDELITY_PAPER_WR_DELTA,
    LAB_MIN_BACKTEST_PF,
    LAB_MIN_BACKTEST_TRADES,
    LAB_PAPER_MIN_TRADES_REJECT,
    LAB_PAPER_MIN_WR,
)


def check_walk_forward_acceptance(train_metrics: dict, test_metrics: dict) -> dict:
    test_pf = test_metrics.get("profit_factor") or 0.0
    test_n = int(test_metrics.get("n") or 0)
    train_wr = float(train_metrics.get("win_rate") or 0.0)
    test_wr = float(test_metrics.get("win_rate") or 0.0)
    min_test_n = max(8, LAB_MIN_BACKTEST_TRADES // 3)
    max_dd = float(test_metrics.get("max_drawdown") or 0.0)
    passed = (
        test_n >= min_test_n
        and test_pf >= FIDELITY_MIN_PF
        and test_wr >= train_wr - 0.15
        and max_dd <= FIDELITY_MAX_DD
    )
    return {
        "passed": passed,
        "test_pf": test_pf,
        "test_n": test_n,
        "test_wr": test_wr,
        "train_wr": train_wr,
        "max_drawdown": max_dd,
        "min_test_n": min_test_n,
    }


def check_backtest_promotion(metrics: dict, walk_forward: dict | None = None) -> dict:
    base_pass = bool(metrics.get("passed"))
    wf_pass = walk_forward.get("passed", True) if walk_forward else True
    dd_ok = float(metrics.get("max_drawdown") or 0.0) <= FIDELITY_MAX_DD
    pf_ok = (metrics.get("profit_factor") or 0.0) >= FIDELITY_MIN_PF
    passed = base_pass and wf_pass and dd_ok and pf_ok
    return {
        "passed": passed,
        "base_pass": base_pass,
        "walk_forward_pass": wf_pass,
        "dd_ok": dd_ok,
        "pf_ok": pf_ok,
    }


def check_kasa_backtest_acceptance(metrics: dict, backtest_days: int) -> dict:
    """90 gun backtest + PF + max DD kapisi."""
    pf = metrics.get("profit_factor") or 0.0
    max_dd = float(metrics.get("max_drawdown") or 0.0)
    n = int(metrics.get("n") or 0)
    passed = (
        backtest_days >= FIDELITY_MIN_BACKTEST_DAYS
        and n >= LAB_MIN_BACKTEST_TRADES
        and pf >= FIDELITY_MIN_PF
        and max_dd <= FIDELITY_MAX_DD
    )
    return {"passed": passed, "backtest_days": backtest_days, "max_drawdown": max_dd, "profit_factor": pf}


def check_paper_acceptance(backtest_metrics: dict, paper_metrics: dict) -> dict:
    bt_wr = float(backtest_metrics.get("win_rate") or 0.0)
    paper_wr = float(paper_metrics.get("wr") or 0.0)
    paper_n = int(paper_metrics.get("n") or 0)
    bt_pf = backtest_metrics.get("profit_factor") or 0.0
    reject = paper_n >= LAB_PAPER_MIN_TRADES_REJECT and (
        paper_wr < LAB_PAPER_MIN_WR
        or paper_wr < bt_wr - FIDELITY_PAPER_WR_DELTA
    )
    promote_ready = (
        paper_n >= LAB_PAPER_MIN_TRADES_REJECT
        and paper_wr >= max(LAB_PAPER_MIN_WR, bt_wr - FIDELITY_PAPER_WR_DELTA)
        and (bt_pf or 0) >= LAB_MIN_BACKTEST_PF
    )
    return {
        "reject": reject,
        "promote_ready": promote_ready,
        "paper_wr": paper_wr,
        "paper_n": paper_n,
        "backtest_wr": bt_wr,
    }
