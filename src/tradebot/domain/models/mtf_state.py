from dataclasses import dataclass
from typing import Optional


@dataclass
class MtfState:
    symbol: str
    regime: str                         # MarketRegime value
    cascade_passed: bool
    score: float
    quality: str                        # SignalQuality value
    active_setup: Optional[str]         # SetupType value | None
    scores_by_tf: dict                  # {"4h": 0.8, "1h": 0.6, ...}
    rejection_reason: Optional[str]
    evaluated_at_ms: int
    signal_open_time_ms: Optional[int] = None
