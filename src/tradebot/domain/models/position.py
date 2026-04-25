from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from typing import Optional

from tradebot.domain.models.exit_plan import ExitPlan


class PositionStatus(str, Enum):
    PENDING_ENTRY = "PENDING_ENTRY"
    OPEN_ENTRY_SENT = "OPEN_ENTRY_SENT"
    ACTIVE = "ACTIVE"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


@dataclass
class Position:
    id: str                             # UUID
    symbol: str
    side: str                           # "BUY" (spot only)
    status: PositionStatus
    entry_price: Decimal
    quantity_total: Decimal
    stop_loss: Decimal
    atr_at_entry: Decimal
    signal_score: float
    setup_type: str                     # "A" | "B" | "C" | "D"
    shard_id: int
    opened_at_ms: int
    exit_plan: ExitPlan
    high_since_entry: Decimal
    closed_at_ms: Optional[int] = None
    last_checked_ms: Optional[int] = None

    @property
    def quantity_remaining(self) -> Decimal:
        filled = sum(
            lot.quantity for lot in self.exit_plan.lots if lot.is_filled
        )
        return self.quantity_total - filled

    def with_status(self, status: PositionStatus) -> "Position":
        return replace(self, status=status)
