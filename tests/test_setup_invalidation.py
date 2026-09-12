from unittest.mock import MagicMock, patch

from engine.setup_invalidation import setup_still_valid
from engine.types import Side
from strategies.patlama_selale import PatlamaSelale


def test_patlama_invalid_when_score_drops():
    strat = PatlamaSelale()
    ctx = MagicMock()
    ctx.aligned.return_value = True
    scored = MagicMock(long_score=3, short_score=1)
    with patch("engine.setup_invalidation.score_momentum", return_value=scored):
        with patch("engine.setup_invalidation.trade_signal_from_score", return_value=None):
            assert setup_still_valid(strat, ctx, Side.BUY) is False


def test_patlama_valid_when_signal_holds():
    strat = PatlamaSelale()
    ctx = MagicMock()
    ctx.aligned.return_value = True
    scored = MagicMock()
    with patch("engine.setup_invalidation.score_momentum", return_value=scored):
        with patch("engine.setup_invalidation.trade_signal_from_score", return_value=Side.BUY):
            assert setup_still_valid(strat, ctx, Side.BUY) is True
