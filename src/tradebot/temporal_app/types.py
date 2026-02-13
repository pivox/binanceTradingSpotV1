from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Timeframe = Literal["1m", "5m", "15m", "1h", "4h"]
Side = Literal["BUY", "SELL"]
IntentStatus = Literal["NEW", "SENT", "ACKED", "FILLED", "REJECTED", "CANCELED"]


@dataclass(frozen=True)
class CandleCloseEvent:
    symbol: str
    timeframe: Timeframe
    open_time_ms: int


@dataclass(frozen=True)
class IndicatorSnapshot:
    symbol: str
    timeframe: Timeframe
    open_time_ms: int
    payload: dict[str, Any]


@dataclass
class MtfState:
    symbol: str
    context_ok_4h: bool = False
    context_ok_1h: bool = False
    ok_15m: bool = False
    ok_5m: bool = False
    last_eval_1m_open_time_ms: int = 0
    retries_4h: int = 0
    retries_1h: int = 0
    retries_15m: int = 0
    retries_5m: int = 0
    next_allowed_eval_at_ms: int = 0


@dataclass
class OrderIntent:
    intent_key: str
    symbol: str
    side: Side
    timeframe: Timeframe
    open_time_ms: int
    payload: dict[str, Any]
    status: IntentStatus = "NEW"


@dataclass
class Position:
    position_id: str
    symbol: str
    shard_id: int
    status: str
    qty_base: float
    avg_entry_price: float
    exit_plan: dict[str, Any]
    next_check_at_ms: int
