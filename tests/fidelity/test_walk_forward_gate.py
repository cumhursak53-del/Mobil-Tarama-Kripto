"""Walk-forward ve fidelity gate unit testleri."""
from engine.fidelity_gate import check_paper_acceptance, check_walk_forward_acceptance


def test_walk_forward_passes_good_test_set():
    train = {"win_rate": 0.55, "n": 40, "profit_factor": 1.4}
    test = {"win_rate": 0.50, "n": 20, "profit_factor": 1.3, "max_drawdown": 0.12}
    out = check_walk_forward_acceptance(train, test)
    assert out["passed"] is True


def test_walk_forward_rejects_low_pf():
    train = {"win_rate": 0.55, "n": 40, "profit_factor": 1.4}
    test = {"win_rate": 0.50, "n": 20, "profit_factor": 0.9, "max_drawdown": 0.12}
    out = check_walk_forward_acceptance(train, test)
    assert out["passed"] is False


def test_walk_forward_rejects_high_dd():
    train = {"win_rate": 0.55, "n": 40, "profit_factor": 1.4}
    test = {"win_rate": 0.50, "n": 20, "profit_factor": 1.3, "max_drawdown": 0.40}
    out = check_walk_forward_acceptance(train, test)
    assert out["passed"] is False


def test_paper_reject_on_underperform():
    bt = {"win_rate": 0.50, "profit_factor": 1.3}
    paper = {"wr": 0.30, "n": 10}
    out = check_paper_acceptance(bt, paper)
    assert out["reject"] is True
