from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class LotRule:
    type: str               # "tp_r_multiple" | "trailing"
    r_multiple: float = 0.0
    atr_tf: str = "5m"
    atr_multiplier: float = 2.0


@dataclass
class Lot:
    id: str                 # "A" | "B" | "C"
    pct: float              # fraction de quantity_total
    rule: LotRule
    quantity: Decimal = Decimal("0")
    is_filled: bool = False
    fill_price: Optional[Decimal] = None
    fill_time_ms: Optional[int] = None
    current_trailing: Optional[Decimal] = None  # niveau courant du trailing stop (Lot C)
    binance_order_id: Optional[int] = None


@dataclass
class ExitPlan:
    lot_a: Lot
    lot_b: Lot
    lot_c: Lot
    r_distance: Decimal = Decimal("0")  # 1R = entry - stop_loss

    @property
    def lots(self) -> list[Lot]:
        return [self.lot_a, self.lot_b, self.lot_c]

    @property
    def all_filled(self) -> bool:
        return self.lot_a.is_filled and self.lot_b.is_filled and self.lot_c.is_filled
