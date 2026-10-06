"""Execution backends: paper (noop) and Bybit live."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from engine.config import (
    BYBIT_API_KEY,
    BYBIT_API_SECRET,
    CLOSE_CONFIRM_POLL_SEC,
    CLOSE_CONFIRM_TIMEOUT_SEC,
    LIVE_LEDGERS,
    LIVE_MAX_NOTIONAL_USD,
    SL_ATTACH_MAX_ATTEMPTS,
    SL_ATTACH_RETRY_DELAY_SEC,
    is_live_exchange,
)
from engine.exchange.bybit_client import BybitClient, BybitError
from engine.types import Position, Signal
from risk.sizer import SizedTrade

# Kapanis emri hala calisiyorsa ikinci market emri gonderme.
WORKING_ORDER_STATUSES = frozenset(
    {"New", "Created", "PartiallyFilled", "Untriggered", "Triggered", "Active"}
)
DEAD_ORDER_STATUSES = frozenset(
    {"Rejected", "Cancelled", "Canceled", "PartiallyFilledCanceled", "Deactivated"}
)


@dataclass
class ExchangeFill:
    ok: bool
    order_id: str = ""
    fill_price: float = 0.0
    fill_qty: float = 0.0
    message: str = ""
    confirmed: bool = False
    filled: bool = False
    sl_protected: bool = False
    flattened: bool = False
    kapanis_dogrulanmadi: bool = False
    close_order_id: str = ""
    entry_price: float = 0.0
    order_status: str = ""


class PaperExecutor:
    def open_position(
        self,
        symbol: str,
        sig: Signal,
        sized: SizedTrade,
        price: float,
    ) -> ExchangeFill:
        return ExchangeFill(
            ok=True,
            fill_price=price,
            entry_price=price,
            fill_qty=sized.qty,
            message="paper",
            confirmed=True,
            filled=True,
            sl_protected=True,
        )

    def close_position(self, position: Position, price: float, reason: str) -> ExchangeFill:
        return ExchangeFill(
            ok=True,
            confirmed=True,
            fill_price=price,
            fill_qty=position.remaining_qty or position.qty,
            message="paper",
        )

    def reduce_position(self, position: Position, qty: float, price: float) -> ExchangeFill:
        return ExchangeFill(ok=True, confirmed=True, fill_price=price, fill_qty=qty, message="paper")

    def amend_sl(self, position: Position, new_sl: float) -> bool:
        return True

    def ensure_stop(self, position: Position) -> bool:
        return True

    def confirm_close(self, symbol: str, order_id: str = "") -> ExchangeFill:
        return ExchangeFill(ok=True, confirmed=True, message="paper")

    def sync_positions(self) -> list[dict]:
        return []


class BybitExecutor:
    def __init__(self, client: BybitClient | None = None):
        self.client = client or BybitClient()

    def _guard_ledger(self, ledger: str) -> None:
        if ledger not in LIVE_LEDGERS:
            raise BybitError(f"Ledger canli listede degil: {ledger}")

    def _position_row(self, symbol: str) -> dict | None:
        fn = getattr(self.client, "get_position_row", None)
        if fn is None:
            return None
        try:
            row = fn(symbol)
        except Exception:
            return None
        return row if isinstance(row, dict) else None

    def _position_size(self, symbol: str) -> float | None:
        row = self._position_row(symbol)
        if row is None:
            return None
        try:
            return float(row.get("size") or 0)
        except (TypeError, ValueError):
            return None

    def _position_has_stop(self, symbol: str) -> bool:
        row = self._position_row(symbol)
        if not row:
            return False
        try:
            size = float(row.get("size") or 0)
            sl = float(row.get("stop_loss") or 0)
        except (TypeError, ValueError):
            return False
        return size > 0 and sl > 0

    def _get_order_safe(self, symbol: str, order_id: str) -> dict | None:
        if not order_id:
            return None
        fn = getattr(self.client, "get_order", None)
        if fn is None:
            return None
        try:
            row = fn(symbol, order_id)
        except Exception:
            return {"status": "unknown", "avg_price": 0.0, "cum_qty": 0.0, "error": True}
        if not isinstance(row, dict):
            return {"status": "unknown", "avg_price": 0.0, "cum_qty": 0.0, "error": True}
        return row

    @staticmethod
    def _tpsl_param_error(exc: BybitError) -> bool:
        msg = str(exc).lower()
        return any(token in msg for token in ("stoploss", "stop loss", "takeprofit", "take profit", "tpsl"))

    def _place_entry(self, symbol: str, side: str, qty: float, sl: float | None, tp: float | None) -> dict:
        try:
            return self.client.place_market_order(
                symbol,
                side,
                qty,
                stop_loss=sl,
                take_profit=tp,
            )
        except BybitError as exc:
            if sl and self._tpsl_param_error(exc):
                print(
                    f"ALARM SL emre eklenemedi {symbol} ({exc}) — emir SL'siz, ardindan trading-stop",
                    flush=True,
                )
                return self.client.place_market_order(symbol, side, qty)
            raise

    def _read_entry_fill(
        self,
        symbol: str,
        order_id: str,
        order: dict,
        fallback_price: float,
        fallback_qty: float,
    ) -> tuple[float, float, bool]:
        avg = float(order.get("avgPrice") or 0)
        qty = float(order.get("cumExecQty") or 0)
        status = str(order.get("orderStatus") or "")
        if status in ("Rejected", "Cancelled", "Canceled"):
            return 0.0, 0.0, False
        if status == "Filled" or (avg > 0 and qty > 0):
            return avg or fallback_price, qty or fallback_qty, True

        deadline = time.monotonic() + max(0.0, float(CLOSE_CONFIRM_TIMEOUT_SEC))
        rejected = {"Rejected", "Cancelled", "Canceled"}
        while True:
            info = self._get_order_safe(symbol, order_id)
            info_status = str((info or {}).get("status") or "")
            size = self._position_size(symbol)
            if info_status == "Filled":
                got_avg = float((info or {}).get("avg_price") or 0) or fallback_price
                got_qty = float((info or {}).get("cum_qty") or 0) or fallback_qty
                return got_avg, got_qty, True
            if size is not None and size > 0:
                return fallback_price, size, True
            if info_status in rejected:
                return 0.0, 0.0, False
            # Boyut 0, emir henuz yeni olabilir — timeout dolmadan "dolmadi" deme.
            if float(CLOSE_CONFIRM_POLL_SEC) <= 0 or time.monotonic() >= deadline:
                if size == 0.0:
                    return 0.0, 0.0, False
                return fallback_price, fallback_qty, True
            time.sleep(float(CLOSE_CONFIRM_POLL_SEC))

    def _ensure_stop(self, symbol: str, sl: float | None, tp: float | None) -> bool:
        if sl is None or float(sl) <= 0:
            return False
        attempts = max(1, int(SL_ATTACH_MAX_ATTEMPTS))
        last_set_ok = False
        for i in range(attempts):
            if self._position_has_stop(symbol):
                return True
            try:
                self.client.set_trading_stop(
                    symbol,
                    stop_loss=float(sl),
                    take_profit=float(tp) if tp and float(tp) > 0 else None,
                )
                last_set_ok = True
            except Exception as exc:
                last_set_ok = False
                print(f"ALARM SL denemesi {i + 1}/{attempts} {symbol}: {exc}", flush=True)
            if self._position_has_stop(symbol):
                return True
            if i < attempts - 1 and float(SL_ATTACH_RETRY_DELAY_SEC) > 0:
                time.sleep(float(SL_ATTACH_RETRY_DELAY_SEC))
        if self._position_has_stop(symbol):
            return True
        # trading-stop kabul edildi ama pozisyon okunamadi — korumayi silme.
        if last_set_ok and self._position_size(symbol) is None:
            return True
        return False

    def ensure_stop(self, position: Position) -> bool:
        tp = position.tp_price if position.tp_price else None
        return self._ensure_stop(position.symbol, position.sl_price, tp)

    def confirm_close(self, symbol: str, order_id: str = "") -> ExchangeFill:
        """Yeni emir gondermez. Boyut > 0 ise kapanis sayilmaz."""
        size = self._position_size(symbol)
        order = self._get_order_safe(symbol, order_id) if order_id else None
        if order and order.get("error"):
            status = "unknown"
        else:
            status = str((order or {}).get("status") or "")
        try:
            avg = float((order or {}).get("avg_price") or 0)
            cum = float((order or {}).get("cum_qty") or 0)
        except (TypeError, ValueError):
            avg, cum = 0.0, 0.0
        if size is not None and size > 0:
            return ExchangeFill(
                ok=False,
                confirmed=False,
                order_id=order_id,
                order_status=status,
                fill_price=avg if avg > 0 else 0.0,
                message="pozisyon boyutu > 0",
            )
        if size == 0.0 or status == "Filled":
            return ExchangeFill(
                ok=True,
                confirmed=True,
                order_id=order_id,
                order_status=status or "Flat",
                fill_price=avg if avg > 0 else 0.0,
                fill_qty=cum,
                message="kapanis_dogrulandi",
            )
        return ExchangeFill(
            ok=False,
            confirmed=False,
            order_id=order_id,
            order_status=status or "unknown",
            message="kapanis dogrulanamadi",
        )

    def _await_close(self, symbol: str, order_id: str, fallback_price: float) -> ExchangeFill:
        deadline = time.monotonic() + max(0.0, float(CLOSE_CONFIRM_TIMEOUT_SEC))
        while True:
            snap = self.confirm_close(symbol, order_id)
            snap.order_id = order_id or snap.order_id
            snap.close_order_id = order_id
            if snap.confirmed:
                if snap.fill_price <= 0 and fallback_price > 0:
                    snap.fill_price = fallback_price
                snap.ok = True
                return snap
            if snap.order_status in DEAD_ORDER_STATUSES:
                snap.ok = False
                snap.confirmed = False
                snap.kapanis_dogrulanmadi = True
                snap.order_id = order_id
                snap.close_order_id = order_id
                snap.message = snap.message or snap.order_status or "kapanis_dogrulanmadi"
                return snap
            timed_out = float(CLOSE_CONFIRM_POLL_SEC) <= 0 or time.monotonic() >= deadline
            if timed_out:
                snap.ok = False
                snap.confirmed = False
                snap.kapanis_dogrulanmadi = True
                snap.order_id = order_id
                snap.close_order_id = order_id
                snap.message = snap.message or "kapanis_dogrulanmadi"
                return snap
            time.sleep(float(CLOSE_CONFIRM_POLL_SEC))

    def _await_order_filled(self, symbol: str, order_id: str) -> ExchangeFill:
        deadline = time.monotonic() + max(0.0, float(CLOSE_CONFIRM_TIMEOUT_SEC))
        while True:
            info = self._get_order_safe(symbol, order_id)
            status = str((info or {}).get("status") or "")
            avg = float((info or {}).get("avg_price") or 0) if info else 0.0
            cum = float((info or {}).get("cum_qty") or 0) if info else 0.0
            if status == "Filled":
                return ExchangeFill(
                    ok=True,
                    confirmed=True,
                    order_id=order_id,
                    order_status=status,
                    fill_price=avg,
                    fill_qty=cum,
                )
            if status in DEAD_ORDER_STATUSES:
                return ExchangeFill(
                    ok=False,
                    confirmed=False,
                    order_id=order_id,
                    order_status=status,
                    message=status or "emir reddedildi",
                )
            if float(CLOSE_CONFIRM_POLL_SEC) <= 0 or time.monotonic() >= deadline:
                return ExchangeFill(
                    ok=False,
                    confirmed=False,
                    order_id=order_id,
                    order_status=status,
                    message="emir dogrulanamadi",
                )
            time.sleep(float(CLOSE_CONFIRM_POLL_SEC))

    def _flatten(self, symbol: str, side: str, qty: float, fallback_price: float) -> ExchangeFill:
        try:
            order = self.client.close_position_market(symbol, side, qty)
        except Exception as exc:
            size = self._position_size(symbol)
            if size == 0.0:
                return ExchangeFill(
                    ok=True,
                    confirmed=True,
                    flattened=True,
                    fill_price=fallback_price,
                    message="zaten_kapali",
                    order_status="Flat",
                )
            return ExchangeFill(
                ok=False,
                confirmed=False,
                kapanis_dogrulanmadi=True,
                message=str(exc),
            )
        order_id = str(order.get("orderId") or "")
        result = self._await_close(symbol, order_id, fallback_price)
        result.flattened = bool(result.confirmed)
        result.close_order_id = order_id
        if not result.confirmed:
            result.kapanis_dogrulanmadi = True
            result.ok = False
        return result

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
        sl = float(sig.sl_price) if sig.sl_price and float(sig.sl_price) > 0 else None
        tp = float(sig.tp_price) if sig.tp_price and float(sig.tp_price) > 0 else None
        try:
            lev = max(1, int(round(sized.leverage)))
            self.client.set_leverage(symbol, lev)
            order = self._place_entry(symbol, sig.side.value, sized.qty, sl, tp)
        except BybitError as exc:
            return ExchangeFill(ok=False, message=str(exc))
        except Exception as exc:
            return ExchangeFill(ok=False, message=f"Bybit open hatasi: {exc}")

        order_id = str(order.get("orderId") or "")
        entry_price, entry_qty, filled = self._read_entry_fill(
            symbol, order_id, order, price, sized.qty
        )
        if not filled:
            return ExchangeFill(ok=False, order_id=order_id, message="Giris emri dolmadi")

        protected = self._ensure_stop(symbol, sl, tp) if sl else False
        if sl and protected:
            return ExchangeFill(
                ok=True,
                order_id=order_id,
                fill_price=entry_price,
                entry_price=entry_price,
                fill_qty=entry_qty,
                message="bybit_open",
                confirmed=True,
                filled=True,
                sl_protected=True,
            )

        print(f"ALARM SL takilamadi {symbol} — reduce-only kapatiliyor", flush=True)
        flat = self._flatten(symbol, sig.side.value, entry_qty, entry_price)
        flat.filled = True
        flat.entry_price = entry_price
        flat.fill_qty = entry_qty
        flat.sl_protected = False
        flat.order_id = order_id
        if flat.confirmed:
            flat.flattened = True
            flat.ok = False
            flat.kapanis_dogrulanmadi = False
            flat.message = "SL takilamadi, reduce-only kapatildi"
            if flat.fill_price <= 0:
                flat.fill_price = entry_price
        else:
            flat.flattened = False
            flat.ok = False
            flat.kapanis_dogrulanmadi = True
            flat.message = flat.message or "SL takilamadi, kapanis dogrulanamadi"
        return flat

    def close_position(self, position: Position, price: float, reason: str) -> ExchangeFill:
        self._guard_ledger(position.ledger)
        qty = position.remaining_qty or position.qty
        if qty <= 0:
            snap = self.confirm_close(position.symbol, position.close_order_id)
            if snap.confirmed:
                if snap.fill_price <= 0:
                    snap.fill_price = price
                return snap
            return ExchangeFill(ok=True, confirmed=True, fill_price=price, fill_qty=0, message="no_qty")
        try:
            order = self.client.close_position_market(position.symbol, position.side.value, qty)
        except BybitError as exc:
            size = self._position_size(position.symbol)
            if size == 0.0:
                return ExchangeFill(
                    ok=True,
                    confirmed=True,
                    fill_price=price,
                    message="zaten_kapali",
                    order_status="Flat",
                )
            return ExchangeFill(ok=False, confirmed=False, kapanis_dogrulanmadi=True, message=str(exc))
        except Exception as exc:
            return ExchangeFill(
                ok=False,
                confirmed=False,
                kapanis_dogrulanmadi=True,
                message=f"Bybit close hatasi: {exc}",
            )
        order_id = str(order.get("orderId") or "")
        return self._await_close(position.symbol, order_id, price)

    def reduce_position(self, position: Position, qty: float, price: float) -> ExchangeFill:
        self._guard_ledger(position.ledger)
        if qty <= 0:
            return ExchangeFill(ok=False, confirmed=False, message="qty<=0")
        try:
            order = self.client.close_position_market(position.symbol, position.side.value, qty)
        except BybitError as exc:
            return ExchangeFill(ok=False, confirmed=False, message=str(exc))
        except Exception as exc:
            return ExchangeFill(ok=False, confirmed=False, message=f"Bybit reduce hatasi: {exc}")
        order_id = str(order.get("orderId") or "")
        avg = float(order.get("avgPrice") or 0)
        done = float(order.get("cumExecQty") or 0)
        status = str(order.get("orderStatus") or "")
        if status == "Filled" or (avg > 0 and done > 0):
            return ExchangeFill(
                ok=True,
                confirmed=True,
                order_id=order_id,
                fill_price=avg or price,
                fill_qty=done or qty,
                order_status=status or "Filled",
                message="bybit_partial",
            )
        filled = self._await_order_filled(position.symbol, order_id)
        if not filled.confirmed:
            filled.ok = False
            filled.message = filled.message or "kismi kapanis dogrulanamadi"
            return filled
        if filled.fill_price <= 0:
            filled.fill_price = price
        if filled.fill_qty <= 0:
            filled.fill_qty = qty
        filled.message = "bybit_partial"
        return filled

    def amend_sl(self, position: Position, new_sl: float) -> bool:
        try:
            self.client.set_trading_stop(position.symbol, stop_loss=new_sl, take_profit=position.tp_price)
            return True
        except Exception:
            return False

    def sync_positions(self) -> list[dict] | None:
        try:
            return self.client.get_positions()
        except Exception:
            return None


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
