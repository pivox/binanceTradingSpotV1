from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


@dataclass(frozen=True)
class BacktestConfig:
    profile: str = "regular"
    slippage_pct: float = 0.0005
    k_atr: float = 2.0
    r_multiple: float = 1.5
    sl_buffer_pct: float = 0.003
    max_sl_pct: float = 0.02
    risk_pct: float = 0.01
    initial_capital_usdc: float = 10000.0
    fees_pct: float = 0.001
    min_closed_trades: int = 20
    mode: Literal["exploration", "phase_gate"] = "exploration"


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    entry_time_ms: int
    entry_price: float
    stop_loss: float
    take_profit: float
    sl_method: Literal["PIVOT", "ATR_FALLBACK"]
    exit_time_ms: int | None
    exit_price: float | None
    exit_reason: Literal["TP", "SL", "OPEN"] | None
    pnl_r: float | None  # P&L in R: +r_multiple (TP) or -1.0 (SL)
    mfe_pct: float | None  # Maximum Favorable Excursion (%)
    mae_pct: float | None  # Maximum Adverse Excursion (%)
    signal_score: int
    signal_context: dict[str, Any]


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class BacktestMetrics:
    total_trades: int
    closed_trades: int
    winning_trades: int
    winrate: float
    profit_factor: float
    max_drawdown_pct: float
    expectancy_r: float
    avg_mfe_pct: float
    avg_mae_pct: float
    passes_phase_gate: bool
    verdict: Verdict = Verdict.INCONCLUSIVE
    verdict_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    symbol: str
    from_ms: int
    to_ms: int
    config: BacktestConfig
    trades: list[BacktestTrade]
    metrics: BacktestMetrics
