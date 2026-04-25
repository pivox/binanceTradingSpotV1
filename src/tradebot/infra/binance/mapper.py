from __future__ import annotations

import structlog
from decimal import Decimal

from tradebot.domain.models.candle import Candle
from tradebot.domain.models.order_intent import OrderIntent, OrderIntentStatus, Side, OrderType
from tradebot.domain.models.symbol_filters import SymbolFilters

log = structlog.get_logger()

_BINANCE_STATUS_MAP = {
    "NEW": OrderIntentStatus.SENT,
    "PARTIALLY_FILLED": OrderIntentStatus.PARTIALLY_FILLED,
    "FILLED": OrderIntentStatus.FILLED,
    "CANCELED": OrderIntentStatus.CANCELLED,
    "EXPIRED": OrderIntentStatus.CANCELLED,
    "REJECTED": OrderIntentStatus.FAILED,
}


class BinanceMapper:

    @staticmethod
    def kline_to_candle(raw: list, symbol: str, timeframe: str) -> Candle:
        return Candle(
            symbol=symbol,
            timeframe=timeframe,
            open_time_ms=int(raw[0]),
            close_time_ms=int(raw[6]),
            open=Decimal(str(raw[1])),
            high=Decimal(str(raw[2])),
            low=Decimal(str(raw[3])),
            close=Decimal(str(raw[4])),
            volume=Decimal(str(raw[5])),
            is_partial=False,
        )

    @staticmethod
    def order_response_to_order_intent(raw: dict, intent_key: str = "") -> OrderIntent:
        status_str = raw.get("status", "NEW")
        status = _BINANCE_STATUS_MAP.get(status_str, OrderIntentStatus.SENT)
        return OrderIntent(
            id=raw.get("clientOrderId", ""),
            intent_key=intent_key,
            symbol=raw["symbol"],
            side=Side(raw["side"]),
            order_type=OrderType(raw["type"]),
            quantity=Decimal(str(raw.get("origQty", "0"))),
            status=status,
            price=Decimal(str(raw["price"])) if raw.get("price") else None,
            stop_price=Decimal(str(raw["stopPrice"])) if raw.get("stopPrice") else None,
            binance_order_id=raw.get("orderId"),
            filled_qty=Decimal(str(raw.get("executedQty", "0"))) or None,
            avg_price=Decimal(str(raw.get("price", "0"))) or None,
            created_at_ms=raw.get("transactTime", 0),
        )

    @staticmethod
    def exchange_info_to_filters(raw: dict) -> dict[str, SymbolFilters]:
        result: dict[str, SymbolFilters] = {}
        for sym_info in raw.get("symbols", []):
            symbol = sym_info["symbol"]
            try:
                filters = {f["filterType"]: f for f in sym_info.get("filters", [])}
                lot = filters.get("LOT_SIZE", {})
                price_f = filters.get("PRICE_FILTER", {})
                notional = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))
                if not lot or not price_f:
                    log.warning("exchange_info_missing_filters", symbol=symbol)
                    continue
                result[symbol] = SymbolFilters(
                    symbol=symbol,
                    step_size=Decimal(str(lot["stepSize"])),
                    min_qty=Decimal(str(lot["minQty"])),
                    max_qty=Decimal(str(lot["maxQty"])),
                    tick_size=Decimal(str(price_f["tickSize"])),
                    min_price=Decimal(str(price_f["minPrice"])),
                    max_price=Decimal(str(price_f["maxPrice"])),
                    min_notional=Decimal(str(notional.get("minNotional", "10"))),
                )
            except (KeyError, Exception):
                log.warning("exchange_info_parse_error", symbol=symbol)
        return result

    @staticmethod
    def account_to_balances(raw: dict) -> dict[str, Decimal]:
        return {
            b["asset"]: Decimal(str(b["free"]))
            for b in raw.get("balances", [])
            if Decimal(str(b["free"])) > Decimal("0")
        }
