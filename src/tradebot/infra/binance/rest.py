from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import aiohttp

from tradebot.config.settings import Settings
from tradebot.infra.binance._signing import add_auth_params
from tradebot.infra.binance.exceptions import (
    BinanceApiError,
    BinanceInvalidQtyError,
    BinanceIpBanError,
    BinanceRateLimitError,
    BinanceServerError,
    BinanceTimeoutError,
)


@dataclass
class RestResponse:
    data: Any
    weight_used: int
    order_count: int


class BinanceRestClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.binance_rest_url.rstrip("/")
        self._api_key = settings.binance_api_key
        self._secret = settings.binance_api_secret
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"X-MBX-APIKEY": self._api_key},
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        signed: bool = False,
        timeout_s: float = 10.0,
    ) -> RestResponse:
        session = await self._get_session()
        p = dict(params or {})
        if signed:
            add_auth_params(p, self._secret)
        url = f"{self._base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=timeout_s)
        try:
            async with session.request(method, url, params=p, timeout=timeout) as resp:
                weight = int(resp.headers.get("X-MBX-USED-WEIGHT-1M", 0))
                order_count = int(resp.headers.get("X-MBX-ORDER-COUNT-10S", 0))
                if resp.status == 418:
                    data = await resp.json()
                    raise BinanceIpBanError(data.get("code", -1), data.get("msg", ""), 418)
                if resp.status == 429:
                    data = await resp.json()
                    raise BinanceRateLimitError(data.get("code", -1), data.get("msg", ""), 429)
                if resp.status >= 500:
                    raise BinanceServerError(f"HTTP {resp.status}")
                data = await resp.json()
                if resp.status >= 400:
                    code = data.get("code", -1)
                    msg = data.get("msg", "")
                    if code in (-1013, -2010):
                        raise BinanceInvalidQtyError(code, msg, resp.status)
                    raise BinanceApiError(code, msg, resp.status)
                return RestResponse(data=data, weight_used=weight, order_count=order_count)
        except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as exc:
            raise BinanceTimeoutError(str(exc)) from exc

    # ── Market endpoints ──────────────────────────────────────────────────────

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 1000,
    ) -> RestResponse:
        params: dict = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms
        return await self._request("GET", "/api/v3/klines", params=params, timeout_s=30.0)

    async def get_ticker_24h(self, symbol: str | None = None) -> RestResponse:
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/api/v3/ticker/24hr", params=params, timeout_s=30.0)

    async def get_exchange_info(self, symbols: list[str] | None = None) -> RestResponse:
        params: dict = {}
        if symbols:
            import json
            params["symbols"] = json.dumps(symbols)
        return await self._request("GET", "/api/v3/exchangeInfo", params=params, timeout_s=30.0)

    # ── Account endpoints ─────────────────────────────────────────────────────

    async def get_account_balances(self) -> RestResponse:
        return await self._request("GET", "/api/v3/account", signed=True)

    # ── Order endpoints ───────────────────────────────────────────────────────

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        client_order_id: str | None = None,
        time_in_force: str = "GTC",
    ) -> RestResponse:
        params: dict = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),
        }
        if order_type == "LIMIT":
            params["timeInForce"] = time_in_force
            if price is not None:
                params["price"] = str(price)
        if stop_price is not None:
            params["stopPrice"] = str(stop_price)
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        try:
            return await self._request("POST", "/api/v3/order", params=params, signed=True)
        except BinanceInvalidQtyError:
            raise
        except BinanceApiError as exc:
            if exc.code == -2010 and client_order_id:
                return await self.get_order(symbol, client_order_id=client_order_id)
            raise

    async def cancel_order(
        self,
        symbol: str,
        order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> RestResponse:
        params: dict = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id
        return await self._request("DELETE", "/api/v3/order", params=params, signed=True)

    async def get_order(
        self,
        symbol: str,
        order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> RestResponse:
        params: dict = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id
        return await self._request("GET", "/api/v3/order", params=params, signed=True)

    async def get_open_orders(self, symbol: str) -> RestResponse:
        return await self._request(
            "GET", "/api/v3/openOrders", params={"symbol": symbol}, signed=True
        )

    # ── Listen key (User Stream) ──────────────────────────────────────────────

    async def create_listen_key(self) -> RestResponse:
        return await self._request("POST", "/api/v3/userDataStream")

    async def renew_listen_key(self, listen_key: str) -> RestResponse:
        return await self._request(
            "PUT", "/api/v3/userDataStream", params={"listenKey": listen_key}
        )

    async def delete_listen_key(self, listen_key: str) -> RestResponse:
        return await self._request(
            "DELETE", "/api/v3/userDataStream", params={"listenKey": listen_key}
        )
