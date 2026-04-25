from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from tradebot.domain.models.signal import SignalQuality, SetupType


class MarketRegime(str, Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    RECOVERY = "RECOVERY"
    VOLATILE = "VOLATILE"


@dataclass
class CascadeResult:
    symbol: str
    regime: MarketRegime
    cascade_passed: bool
    score: float
    quality: SignalQuality
    active_setup: Optional[SetupType]
    scores_by_tf: dict              # {"4h": 0.8, "1h": 0.6, ...}
    rejection_reason: Optional[str]
    evaluated_at_ms: int
