from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass(frozen=True)
class OrderIntent:
    intent_key: str
    symbol: str
    side: Side
    order_type: OrderType
    qty: float
    price: Optional[float] = None
    client_order_id: Optional[str] = None
