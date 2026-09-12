from strategies.smc import _in_ob_zone, _resolve_smc_entry
from engine.types import Side


class _Ob:
    def __init__(self, bottom, top):
        self.bottom = bottom
        self.top = top


def test_in_ob_zone():
    ob = _Ob(98.0, 102.0)
    assert _in_ob_zone(100.0, ob)
    assert not _in_ob_zone(95.0, ob)


def test_resolve_smc_entry_near_limit():
    mode, limit = _resolve_smc_entry(100.0, Side.BUY, 100.5, "limit")
    assert mode == "market"
    assert limit is None


def test_resolve_smc_entry_far_limit():
    mode, limit = _resolve_smc_entry(110.0, Side.BUY, 100.0, "limit")
    assert mode == "limit"
    assert limit == 100.0
