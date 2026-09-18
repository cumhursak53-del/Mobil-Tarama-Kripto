"""Execution backends: paper (noop) and Bybit live."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine.config import (
    BYBIT_API_KEY,
    BYBIT_API_SECRET,
    LIVE_LEDGERS,
    LIVE_MAX_NOTIONAL_USD,
    is_live_exchange,
)
from engine.exchange.bybit_client import BybitClient, BybitError
from engine.types import Position, Signal
from risk.sizer import SizedTrade


@dataclass
class ExchangeFill:
    ok: bool
    order_id: str = ""
    fill_price: float = 0.0
    fill_qty: float = 0.0
    message: str = ""


class PaperExecutor:
    def open_position(
        self,
        symbol: str,
        sig: Signal,
        sized: SizedTrade,
        price: float,
    ) -> ExchangeFill:
        return ExchangeFill(ok=True, fill_price=price, fill_qty=sized.qty, message="paper")

    def close_position(self, position: Position, price: float, reason: str) -> ExchangeFill:
        return ExchangeFill(ok=True, fill_price=price, fill_qty=position.remaining_qty or position.qty)

    def reduce_position(self, position: Position, qty: float, price: float) -> ExchangeFill:
        return ExchangeFill(ok=True, fill_price=price, fill_qty=qty)

    def amend_sl(self, position: Position, new_sl: float) -> bool:
        return True

    def sync_positions(self) -> list[dict]:
        return []


class BybitExecutor:
    def __init__(self, client: BybitClient | None = None):
        self.client = client or BybitClient()

    def _guard_ledger(self, ledger: str) -> None:
        if ledger not in LIVE_LEDGERS:
            raise BybitError(f"Ledger canli listede degil: {ledger}")

    def open_position(
        self,
        symbol: str,
        sig: Signal,
        sized: SizedTrade,
        price: float,
    ) -> ExchangeFill:
        self._guard_ledger(sig.ledger)
        if LIVE_MAX_NOTIONAL_USD > 0 and sized.notional > LIVE_MAX_NOTIONAL_USD:
            return ExchangeFill(
                ok=False,
                message=f"Notional limiti asildi (${sized.notional:.2f} > ${LIVE_MAX_NOTIONAL_USD:.2f})",
            )
        try:
            lev = max(1, int(round(sized.leverage)))
            self.client.set_leverage(symbol, lev)
            order = self.client.place_market_order(symbol, sig.side.value, sized.qty)
            order_id = str((order.get("orderId") or ""))
            fill_price = float(order.get("avgPrice") or price or 0) or price
            fill_qty = float(order.get("cumExecQty") or sized.qty)
            if sig.sl_price > 0 or sig.tp_price:
                self.client.set_trading_stop(
                    symbol,
                    stop_loss=sig.sl_price if sig.sl_price > 0 else None,
                    take_profit=sig.tp_price,
                )
            return ExchangeFill(
                ok=True,
                order_id=order_id,
                fill_price=fill_price,
                fill_qty=fill_qty,
                message="bybit_open",
            )
        except BybitError as e:
            return ExchangeFill(ok=False, message=str(e))
        except Exception as e:
            return ExchangeFill(ok=False, message=f"Bybit open hatasi: {e}")

    def close_position(self, position: Position, price: float, reason: str) -> ExchangeFill:
        self._guard_ledger(position.ledger)
        qty = position.remaining_qty or position.qty
        if qty <= 0:
            return ExchangeFill(ok=True, fill_price=price, fill_qty=0, message="no_qty")
        try:
            order = self.client.close_position_market(position.symbol, position.side.value, qty)
            order_id = str((order.get("orderId") or ""))
            fill_price = float(order.get("avgPrice") or price or 0) or price
            fill_qty = float(order.get("cumExecQty") or qty)
            return ExchangeFill(
                ok=True,
                order_id=order_id,
                fill_price=fill_price,
                fill_qty=fill_qty,
                message=f"bybit_close:{reason}",
            )
        except BybitError as e:
            return ExchangeFill(ok=False, message=str(e))
        except Exception as e:
            return ExchangeFill(ok=False, message=f"Bybit close hatasi: {e}")

    def reduce_position(self, position: Position, qty: float, price: float) -> ExchangeFill:
        self._guard_ledger(position.ledger)
        if qty <= 0:
            return ExchangeFill(ok=False, message="qty<=0")
        try:
            order = self.client.close_position_market(position.symbol, position.side.value, qty)
            fill_price = float(order.get("avgPrice") or price or 0) or price
            fill_qty = float(order.get("cumExecQty") or qty)
            return ExchangeFill(ok=True, fill_price=fill_price, fill_qty=fill_qty, message="bybit_partial")
        except BybitError as e:
            return ExchangeFill(ok=False, message=str(e))

    def amend_sl(self, position: Position, new_sl: float) -> bool:
        try:
            self.client.set_trading_stop(position.symbol, stop_loss=new_sl, take_profit=position.tp_price)
            return True
        except Exception:
            return False

    def sync_positions(self) -> list[dict]:
        try:
            return self.client.get_positions()
        except Exception:
            return []


_EXECUTOR: Optional[object] = None


def get_executor():
    global _EXECUTOR
    if _EXECUTOR is not None:
        return _EXECUTOR
    if is_live_exchange() and BYBIT_API_KEY and BYBIT_API_SECRET:
        _EXECUTOR = BybitExecutor()
    else:
        _EXECUTOR = PaperExecutor()
    return _EXECUTOR


def reset_executor() -> None:
    global _EXECUTOR
    _EXECUTOR = None
