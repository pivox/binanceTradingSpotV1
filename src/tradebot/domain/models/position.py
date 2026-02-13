from dataclasses import dataclass
from enum import Enum
from typing import Optional

from tradebot.domain.models.exit_plan import ExitPlan


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class Position:
    position_id: str
    symbol: str
    status: PositionStatus
    qty: float
    avg_entry: float
    exit_plan: ExitPlan
    next_check_at_ms: Optional[int] = None
