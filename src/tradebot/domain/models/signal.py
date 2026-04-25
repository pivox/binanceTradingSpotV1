from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class SignalReason(str, Enum):
    MTF_OK = "mtf_ok"
    MTF_FAIL = "mtf_fail"


class SignalQuality(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    REJECTED = "REJECTED"


class SetupType(str, Enum):
    A = "A"  # Pullback EMA en tendance
    B = "B"  # Breakout de range
    C = "C"  # Rebond sur pivot + VWAP
    D = "D"  # Golden Cross initiation


@dataclass(frozen=True)
class Signal:
    symbol: str
    setup: SetupType
    quality: SignalQuality
    score: float
    entry_price: Decimal
    stop_loss: Decimal
    tp_lot_a: Decimal
    tp_lot_b: Decimal
    r_distance: Decimal
    atr_1m: Decimal
    risk_pct: float
    cascade_score: float
    created_at_ms: int
    expires_at_ms: int
    trigger_candle_open_ms: int
