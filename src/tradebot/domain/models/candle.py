from dataclasses import dataclass
from enum import Enum


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"


@dataclass(frozen=True)
class Candle:
    symbol: str
    tf: str
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True
