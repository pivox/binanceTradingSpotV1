from __future__ import annotations

from tradebot.services.backtesting.models import BacktestMetrics, BacktestTrade, Verdict


def compute_metrics(
    trades: list[BacktestTrade],
    risk_pct: float = 0.01,
    min_closed_trades: int = 20,
) -> BacktestMetrics:
    closed = [
        t for t in trades if t.exit_reason in ("TP", "SL") and t.pnl_r is not None
    ]

    if not closed:
        return BacktestMetrics(
            total_trades=len(trades),
            closed_trades=0,
            winning_trades=0,
            winrate=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            expectancy_r=0.0,
            avg_mfe_pct=0.0,
            avg_mae_pct=0.0,
            passes_phase_gate=False,
            verdict=Verdict.INCONCLUSIVE,
            verdict_reasons=[f"Not enough closed trades: 0 < {min_closed_trades}"],
        )

    winners = [t for t in closed if t.pnl_r > 0]  # type: ignore[operator]
    losers = [t for t in closed if t.pnl_r <= 0]  # type: ignore[operator]

    winrate = len(winners) / len(closed)
    gross_profit = sum(t.pnl_r for t in winners)  # type: ignore[misc]
    gross_loss = abs(sum(t.pnl_r for t in losers))  # type: ignore[misc]
    profit_factor = gross_profit / gross_loss if gross_loss > 0.0 else float("inf")
    expectancy_r = sum(t.pnl_r for t in closed) / len(closed)  # type: ignore[misc]

    equity = 0.0
    peak = 0.0
    max_dd_r = 0.0
    for t in closed:
        equity += t.pnl_r  # type: ignore[operator]
        peak = max(peak, equity)
        max_dd_r = max(max_dd_r, peak - equity)
    max_drawdown_pct = max_dd_r * risk_pct * 100.0

    mfe_vals = [t.mfe_pct for t in closed if t.mfe_pct is not None]
    mae_vals = [t.mae_pct for t in closed if t.mae_pct is not None]
    avg_mfe = sum(mfe_vals) / len(mfe_vals) if mfe_vals else 0.0
    avg_mae = sum(mae_vals) / len(mae_vals) if mae_vals else 0.0

    passes = winrate > 0.50 and profit_factor > 1.3 and max_drawdown_pct < 15.0

    if len(closed) < min_closed_trades:
        verdict = Verdict.INCONCLUSIVE
        verdict_reasons = [
            f"Not enough closed trades: {len(closed)} < {min_closed_trades}"
        ]
    elif passes:
        verdict = Verdict.PASS
        verdict_reasons = []
    else:
        verdict = Verdict.FAIL
        verdict_reasons = []
        if winrate <= 0.50:
            verdict_reasons.append(f"Winrate too low: {winrate * 100:.1f}% <= 50%")
        if profit_factor <= 1.3:
            verdict_reasons.append(f"Profit factor too low: {profit_factor:.2f} <= 1.3")
        if max_drawdown_pct >= 15.0:
            verdict_reasons.append(
                f"Max drawdown too high: {max_drawdown_pct:.1f}% >= 15%"
            )

    return BacktestMetrics(
        total_trades=len(trades),
        closed_trades=len(closed),
        winning_trades=len(winners),
        winrate=winrate,
        profit_factor=profit_factor,
        max_drawdown_pct=max_drawdown_pct,
        expectancy_r=expectancy_r,
        avg_mfe_pct=avg_mfe,
        avg_mae_pct=avg_mae,
        passes_phase_gate=passes,
        verdict=verdict,
        verdict_reasons=verdict_reasons,
    )
