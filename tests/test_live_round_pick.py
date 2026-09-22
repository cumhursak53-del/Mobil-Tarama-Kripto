from engine.live_round_pick import (
    collect_round_candidate,
    expected_profit_usd,
    log_round_summary,
    rank_round_candidates,
    tp_r_multiple,
    RoundCandidate,
)
from engine.types import Side, Signal


class _Ctx:
    def aligned(self, side) -> bool:
        return True


class _Pf:
    ledgers = {"Kasa_Canli": 100.0}


def _sig(*, tp_price=None, tp_r=2.5) -> Signal:
    return Signal(
        side=Side.BUY,
        strategy="[STRAT: Test]",
        ledger="Kasa_Hacim",
        reason="test",
        sl_price=95.0,
        tp_price=tp_price,
        tp_r=tp_r,
        strength=2.0,
    )


def test_tp_r_multiple_uses_tp_price():
    sig = _sig(tp_price=110.0)
    assert tp_r_multiple(sig, 100.0) == 2.0


def test_expected_profit_scales_with_r():
    sig = _sig(tp_price=112.5)
    profit = expected_profit_usd(_Pf(), 100.0, sig, ledger="Kasa_Canli")
    assert profit > 0


def test_collect_round_candidate_filters_invalid():
    sig = _sig(tp_price=112.5)
    out = collect_round_candidate(
        _Pf(),
        symbol="BTCUSDT",
        strategy=object(),
        ctx=_Ctx(),
        entry=100.0,
        sig=sig,
        strength=2.0,
    )
    assert out is not None
    assert out.symbol == "BTCUSDT"
    assert out.expected_profit_usd > 0


def test_log_round_summary_empty():
    logs: list[str] = []
    log_round_summary([], logs.append, scan_only=True)
    assert logs == ["Tur sinyal secimi: aday yok"]


def test_rank_round_candidates_orders_by_expected_profit():
    low = RoundCandidate("AAAUSDT", object(), _sig(tp_price=110.0), 100.0, 1.0, 1.0)
    high = RoundCandidate("BTCUSDT", object(), _sig(tp_price=120.0), 100.0, 1.0, 2.0)
    ranked = rank_round_candidates([low, high])
    assert ranked[0].symbol == "BTCUSDT"
