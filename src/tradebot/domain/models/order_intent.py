from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"


class OrderIntentStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class OrderIntent:
    id: str                             # UUID
    intent_key: str                     # clé d'idempotence
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    status: OrderIntentStatus = OrderIntentStatus.PENDING
    price: Optional[Decimal] = None     # None si MARKET
    stop_price: Optional[Decimal] = None
    lot_id: Optional[str] = None        # "A" | "B" | "C" (pour SELL)
    position_id: Optional[str] = None
    binance_order_id: Optional[int] = None
    filled_qty: Optional[Decimal] = None
    avg_price: Optional[Decimal] = None
    error_msg: Optional[str] = None
    created_at_ms: int = 0
    updated_at_ms: int = 0
