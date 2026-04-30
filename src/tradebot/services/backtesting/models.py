from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class BacktestConfig:
    profile: str = "regular"
    slippage_pct: float = 0.0005    # 0.05% slippage on entry
    k_atr: float = 2.0              # ATR × k for SL fallback
    r_multiple: float = 1.5         # TP = entry + dist_SL × r_multiple
    sl_buffer_pct: float = 0.003    # 0.3% buffer below pivot support
    max_sl_pct: float = 0.02        # max 2% SL distance from entry
    risk_pct: float = 0.01          # 1% capital risk per trade (for drawdown calc)


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
    pnl_r: float | None            # P&L in R: +r_multiple (TP) or -1.0 (SL)
    mfe_pct: float | None          # Maximum Favorable Excursion (%)
    mae_pct: float | None          # Maximum Adverse Excursion (%)
    signal_score: int
    signal_context: dict[str, Any]


@dataclass(frozen=True)
class BacktestMetrics:
    total_trades: int
    closed_trades: int
    winning_trades: int
    winrate: float
    profit_factor: float
    max_drawdown_pct: float        # peak-to-trough drawdown as % of capital
    expectancy_r: float            # average R per closed trade
    avg_mfe_pct: float
    avg_mae_pct: float
    passes_phase_gate: bool        # winrate > 50% AND PF > 1.3 AND drawdown < 15%


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    symbol: str
    from_ms: int
    to_ms: int
    config: BacktestConfig
    trades: list[BacktestTrade]
    metrics: BacktestMetrics
