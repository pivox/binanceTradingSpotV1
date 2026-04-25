from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class ExitReason(str, Enum):
    TP_LOT_A = "TP_LOT_A"
    TP_LOT_B = "TP_LOT_B"
    TRAILING_STOP_C = "TRAILING_STOP_C"
    FORCED_DEATH_CROSS = "FORCED_DEATH_CROSS"
    FORCED_RSI_EXTREME = "FORCED_RSI_EXTREME"
    FORCED_EMA200 = "FORCED_EMA200"
    FORCED_TIMEOUT = "FORCED_TIMEOUT"
    FORCED_DRY_VOLUME = "FORCED_DRY_VOLUME"
    SL_GLOBAL = "SL_GLOBAL"


@dataclass
class ExitIntent:
    position_id: str
    lot_id: str                         # "A" | "B" | "C" | "ALL" | "BC" | "NONE"
    reason: ExitReason
    quantity: Decimal                   # 0 = mise à jour de niveau, pas de vente
    order_type: str                     # "LIMIT" | "MARKET" | "STOP_MARKET"
    price: Optional[Decimal] = None
    new_stop_loss: Optional[Decimal] = None
    new_trailing_level: Optional[Decimal] = None
