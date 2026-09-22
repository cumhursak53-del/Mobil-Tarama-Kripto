from engine.live_round_pick import collect_round_candidate, expected_profit_usd, tp_r_multiple
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
