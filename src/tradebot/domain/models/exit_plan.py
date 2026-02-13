from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class LotRule:
    type: str
    params: Dict[str, float]


@dataclass(frozen=True)
class Lot:
    id: str
    pct: float
    rule: LotRule


@dataclass(frozen=True)
class ExitPlan:
    lots: List[Lot]
