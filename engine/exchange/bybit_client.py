"""Bybit v5 REST client (testnet + mainnet)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlencode

import requests

from engine.config import BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_BASE_URL, BYBIT_RECV_WINDOW


class BybitError(Exception):
    def __init__(self, message: str, *, ret_code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.ret_code = ret_code
        self.payload = payload or {}


class BybitClient:
    def __init__(
        self,
        *,
        api_key: str = BYBIT_API_KEY,
        api_secret: str = BYBIT_API_SECRET,
        base_url: str = BYBIT_BASE_URL,
        recv_window: int = BYBIT_RECV_WINDOW,
        timeout: float = 15.0,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.recv_window = recv_window
        self.timeout = timeout
        self._instrument_cache: dict[str, dict] = {}

    def _sign(self, payload: str, ts: str) -> str:
        raw = f"{ts}{self.api_key}{self.recv_window}{payload}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            raw.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        if not self.api_key or not self.api_secret:
            raise BybitError("BYBIT_API_KEY / BYBIT_API_SECRET eksik")
        params = dict(params or {})
        body = dict(body or {})
        ts = str(int(time.time() * 1000))
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": str(self.recv_window),
            "Content-Type": "application/json",
        }
        if method.upper() == "GET":
            query = urlencode({k: v for k, v in params.items() if v is not None})
            headers["X-BAPI-SIGN"] = self._sign(query, ts)
            url = f"{self.base_url}{path}"
            if query:
                url = f"{url}?{query}"
            resp = requests.get(url, headers=headers, timeout=self.timeout)
        else:
            payload = json.dumps(body) if body else ""
            headers["X-BAPI-SIGN"] = self._sign(payload, ts)
            resp = requests.post(
                f"{self.base_url}{path}",
                headers=headers,
                data=payload,
                timeout=self.timeout,
            )
        try:
            data = resp.json()
        except Exception as e:
            raise BybitError(f"Bybit JSON hatasi: {e} | HTTP {resp.status_code}") from e
        if resp.status_code >= 400:
            raise BybitError(
                f"HTTP {resp.status_code}: {data.get('retMsg', resp.text)}",
                ret_code=data.get("retCode"),
                payload=data,
            )
        ret_code = int(data.get("retCode", 0))
        if ret_code != 0:
            raise BybitError(
                data.get("retMsg") or "Bybit API hatasi",
                ret_code=ret_code,
                payload=data,
            )
        return data.get("result") or {}

    def get_wallet_balance(self, coin: str = "USDT") -> float:
        result = self._request(
            "GET",
            "/v5/account/wallet-balance",
            params={"accountType": "UNIFIED", "coin": coin},
        )
        for acct in result.get("list") or []:
            for c in acct.get("coin") or []:
                if c.get("coin") == coin:
                    for key in ("walletBalance", "equity", "availableToWithdraw"):
                        val = c.get(key)
                        if val not in (None, ""):
                            return float(val)
        return 0.0

    def get_instrument(self, symbol: str) -> dict:
        sym = symbol.upper()
        if sym in self._instrument_cache:
            return self._instrument_cache[sym]
        result = self._request(
            "GET",
            "/v5/market/instruments-info",
            params={"category": "linear", "symbol": sym},
        )
        rows = result.get("list") or []
        if not rows:
            raise BybitError(f"Sembol bulunamadi: {sym}")
        info = rows[0]
        lot = info.get("lotSizeFilter") or {}
        price = info.get("priceFilter") or {}
        parsed = {
            "symbol": sym,
            "qty_step": float(lot.get("qtyStep") or "0.001"),
            "min_qty": float(lot.get("minOrderQty") or lot.get("qtyStep") or "0.001"),
            "tick_size": float(price.get("tickSize") or "0.01"),
        }
        self._instrument_cache[sym] = parsed
        return parsed

    @staticmethod
    def _round_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        return round(round(value / step) * step, 8)

    def format_qty(self, symbol: str, qty: float) -> str:
        info = self.get_instrument(symbol)
        q = max(info["min_qty"], self._round_step(qty, info["qty_step"]))
        step = info["qty_step"]
        decimals = max(0, len(str(step).split(".")[-1].rstrip("0")) if "." in str(step) else 0)
        return f"{q:.{decimals}f}".rstrip("0").rstrip(".") or str(info["min_qty"])

    def format_price(self, symbol: str, price: float) -> str:
        info = self.get_instrument(symbol)
        p = self._round_step(price, info["tick_size"])
        tick = info["tick_size"]
        decimals = max(0, len(str(tick).split(".")[-1].rstrip("0")) if "." in str(tick) else 0)
        return f"{p:.{decimals}f}"

    def set_leverage(self, symbol: str, leverage: int) -> None:
        try:
            self._request(
                "POST",
                "/v5/position/set-leverage",
                body={
                    "category": "linear",
                    "symbol": symbol.upper(),
                    "buyLeverage": str(leverage),
                    "sellLeverage": str(leverage),
                },
            )
        except BybitError as e:
            # 110043: leverage zaten ayarli — sorun degil
            if e.ret_code == 110043 or "not modified" in str(e).lower():
                return
            raise

    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        *,
        reduce_only: bool = False,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "category": "linear",
            "symbol": symbol.upper(),
            "side": "Buy" if side.upper() in ("BUY", "LONG") else "Sell",
            "orderType": "Market",
            "qty": self.format_qty(symbol, qty),
            "positionIdx": 0,
        }
        if reduce_only:
            body["reduceOnly"] = True
        if stop_loss is not None and float(stop_loss) > 0:
            body["stopLoss"] = self.format_price(symbol, float(stop_loss))
            body["slTriggerBy"] = "MarkPrice"
        if take_profit is not None and float(take_profit) > 0:
            body["takeProfit"] = self.format_price(symbol, float(take_profit))
            body["tpTriggerBy"] = "MarkPrice"
        if body.get("stopLoss") or body.get("takeProfit"):
            body["tpslMode"] = "Full"
        return self._request("POST", "/v5/order/create", body=body)

    def set_trading_stop(
        self,
        symbol: str,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "category": "linear",
            "symbol": symbol.upper(),
            "positionIdx": 0,
            "tpslMode": "Full",
        }
        if stop_loss is not None:
            body["stopLoss"] = self.format_price(symbol, stop_loss)
        if take_profit is not None:
            body["takeProfit"] = self.format_price(symbol, take_profit)
        if len(body) <= 3:
            return {}
        return self._request("POST", "/v5/position/trading-stop", body=body)

    @staticmethod
    def _parse_position_row(row: dict) -> dict[str, Any]:
        size = float(row.get("size") or 0)
        side_raw = (row.get("side") or "").lower()
        if side_raw == "buy":
            side = "BUY"
        elif side_raw == "sell":
            side = "SELL"
        else:
            side = ""
        return {
            "symbol": row.get("symbol"),
            "side": side,
            "size": size,
            "entry_price": float(row.get("avgPrice") or 0),
            "unrealised_pnl": float(row.get("unrealisedPnl") or 0),
            "leverage": float(row.get("leverage") or 1),
            "stop_loss": float(row.get("stopLoss") or 0) or None,
            "take_profit": float(row.get("takeProfit") or 0) or None,
        }

    @staticmethod
    def _pick_position_row(rows: list[dict]) -> dict | None:
        if not rows:
            return None
        def _idx(row: dict) -> int:
            try:
                return int(row.get("positionIdx") or 0)
            except (TypeError, ValueError):
                return 0

        indexed = [r for r in rows if _idx(r) == 0]
        pool = indexed or rows
        active = [r for r in pool if float(r.get("size") or 0) > 0]
        return (active or pool)[0]

    def get_position_row(self, symbol: str) -> dict[str, Any]:
        """Tek sembol. Boyut 0 ise pozisyon kapali demektir (API hatasi degil)."""
        result = self._request(
            "GET",
            "/v5/position/list",
            params={"category": "linear", "symbol": symbol.upper()},
        )
        row = self._pick_position_row(result.get("list") or [])
        if row is None:
            return {
                "symbol": symbol.upper(),
                "side": "",
                "size": 0.0,
                "entry_price": 0.0,
                "unrealised_pnl": 0.0,
                "leverage": 1.0,
                "stop_loss": None,
                "take_profit": None,
            }
        parsed = self._parse_position_row(row)
        parsed["symbol"] = parsed.get("symbol") or symbol.upper()
        return parsed

    def get_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        params = {
            "category": "linear",
            "symbol": symbol.upper(),
            "orderId": order_id,
        }
        for path in ("/v5/order/realtime", "/v5/order/history"):
            result = self._request("GET", path, params=params)
            rows = result.get("list") or []
            if not rows:
                continue
            row = rows[0]
            return {
                "order_id": str(row.get("orderId") or order_id),
                "status": str(row.get("orderStatus") or ""),
                "avg_price": float(row.get("avgPrice") or 0),
                "cum_qty": float(row.get("cumExecQty") or 0),
            }
        return {"order_id": order_id, "status": "", "avg_price": 0.0, "cum_qty": 0.0}

    def get_positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params_base: dict[str, Any] = {"category": "linear", "settleCoin": "USDT", "limit": 200}
        if symbol:
            params_base["symbol"] = symbol.upper()
        out: list[dict[str, Any]] = []
        cursor = ""
        seen: set[str] = set()
        for _ in range(10):
            params = dict(params_base)
            if cursor:
                params["cursor"] = cursor
            result = self._request("GET", "/v5/position/list", params=params)
            for row in result.get("list") or []:
                parsed = self._parse_position_row(row)
                if parsed["size"] <= 0:
                    continue
                out.append(parsed)
            cursor = str(result.get("nextPageCursor") or "")
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
        return out

    def close_position_market(self, symbol: str, side: str, qty: float) -> dict[str, Any]:
        body = {
            "category": "linear",
            "symbol": symbol.upper(),
            "side": "Sell" if side.upper() in ("BUY", "LONG") else "Buy",
            "orderType": "Market",
            "qty": self.format_qty(symbol, qty),
            "reduceOnly": True,
            "positionIdx": 0,
        }
        return self._request("POST", "/v5/order/create", body=body)

    def cancel_all(self, symbol: str) -> None:
        self._request(
            "POST",
            "/v5/order/cancel-all",
            body={"category": "linear", "symbol": symbol.upper()},
        )

    def ping(self) -> bool:
        try:
            self._request("GET", "/v5/market/time")
            return True
        except Exception:
            return False
