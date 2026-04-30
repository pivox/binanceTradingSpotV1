from __future__ import annotations

import dataclasses

from sqlalchemy.orm import Session

from tradebot.infra.db.models import BacktestRun, BacktestTradeRecord
from tradebot.services.backtesting.models import BacktestResult


class BacktestRepoSql:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_result(self, result: BacktestResult) -> None:
        m = result.metrics
        run = BacktestRun(
            id=result.run_id,
            symbol=result.symbol,
            from_ms=result.from_ms,
            to_ms=result.to_ms,
            profile=result.config.profile,
            config_json=dataclasses.asdict(result.config),
            total_trades=m.total_trades,
            closed_trades=m.closed_trades,
            winning_trades=m.winning_trades,
            winrate=m.winrate,
            profit_factor=m.profit_factor,
            max_drawdown_pct=m.max_drawdown_pct,
            expectancy_r=m.expectancy_r,
            avg_mfe_pct=m.avg_mfe_pct,
            avg_mae_pct=m.avg_mae_pct,
            passes_phase_gate=m.passes_phase_gate,
        )
        self._session.add(run)
        for trade in result.trades:
            self._session.add(BacktestTradeRecord(
                run_id=result.run_id,
                symbol=trade.symbol,
                entry_time_ms=trade.entry_time_ms,
                entry_price=trade.entry_price,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
                sl_method=trade.sl_method,
                exit_time_ms=trade.exit_time_ms,
                exit_price=trade.exit_price,
                exit_reason=trade.exit_reason,
                pnl_r=trade.pnl_r,
                mfe_pct=trade.mfe_pct,
                mae_pct=trade.mae_pct,
                signal_score=trade.signal_score,
                signal_context_json=trade.signal_context,
            ))
        self._session.commit()
