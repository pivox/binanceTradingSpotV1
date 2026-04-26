from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class LotRuleConfig:
    type: str
    params: Dict[str, float]


@dataclass(frozen=True)
class LotConfig:
    id: str
    pct: float
    rule: LotRuleConfig


@dataclass(frozen=True)
class ExitPlanConfig:
    lots: List[LotConfig]


@dataclass(frozen=True)
class StrategyConfig:
    mtf_cascade: List[str]
    max_open_positions: int
    per_trade_quote_budget: float
    exit_plan: ExitPlanConfig
    daily_loss_limit_usdc: float = -50.0


@dataclass(frozen=True)
class SchedulesConfig:
    candles_tick_sec: int
    positions_tick_sec: int
    reconcile_klines_min: int
    reconcile_orders_min: int
    exchangeinfo_daily: str


@dataclass(frozen=True)
class ShardingConfig:
    shard_count: int


@dataclass(frozen=True)
class AppConfig:
    sharding: ShardingConfig
    timeframes: List[str]
    schedules: SchedulesConfig
    strategy: StrategyConfig
