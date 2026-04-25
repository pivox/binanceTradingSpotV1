from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SymbolFilters:
    symbol: str
    step_size: Decimal      # LOT_SIZE step
    min_qty: Decimal
    max_qty: Decimal
    tick_size: Decimal      # PRICE_FILTER tick
    min_price: Decimal
    max_price: Decimal
    min_notional: Decimal
