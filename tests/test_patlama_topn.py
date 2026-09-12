from engine.patlama_topn import rank_patlama_candidates, select_top_n
from engine.types import Side


def test_rank_excludes_watch_only():
    scan = {
        "ONEUSDT": {"long_score": 0, "short_score": 3},
        "MAGICUSDT": {"long_score": 1, "short_score": 5},
        "WEAKUSDT": {"long_score": 4, "short_score": 2},
    }
    longs, shorts = rank_patlama_candidates(scan)
    assert len(longs) == 0
    assert len(shorts) == 1
    assert shorts[0][0] == "MAGICUSDT"


def test_select_top_n_per_side():
    scan = {
        "A": {"long_score": 6, "short_score": 1},
        "B": {"long_score": 5, "short_score": 0},
        "C": {"long_score": 0, "short_score": 6},
        "D": {"long_score": 1, "short_score": 5},
    }
    picks = select_top_n(scan, top_n=1)
    assert len(picks) == 2
    assert ("A", Side.BUY, 6) in picks
    assert ("C", Side.SELL, 6) in picks
