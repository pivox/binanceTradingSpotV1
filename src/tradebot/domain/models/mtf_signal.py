from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MTFSignal:
    symbol: str
    profile: str
    trend_4h: bool
    trend_1h: bool
    structure_15m: bool
    trigger_5m: bool
    score: int                        # 0-100
    valid: bool
    blocking_filter: str | None       # filtre bloquant actif, sinon None
    context_json: dict[str, Any]      # détail condition par condition (audit)
    evaluated_at_ms: int
