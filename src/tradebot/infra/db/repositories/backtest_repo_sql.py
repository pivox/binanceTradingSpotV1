from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradebot.infra.db.models import BacktestRun, BacktestTradeRecord
from tradebot.services.backtesting.models import BacktestResult

_MIN_CLOSED_DEFAULT = 20


def _verdict_from_row(row: BacktestRun) -> str:
    config = row.config_json or {}
    min_closed = config.get("min_closed_trades", _MIN_CLOSED_DEFAULT)
    if row.closed_trades < min_closed:
        return "INCONCLUSIVE"
    if row.passes_phase_gate:
        return "PASS"
    return "FAIL"


def _run_to_dict(row: BacktestRun) -> dict:
    return {
        "run_id": row.id,
        "symbol": row.symbol,
        "from_ms": row.from_ms,
        "to_ms": row.to_ms,
        "profile": row.profile,
        "config": row.config_json,
        "total_trades": row.total_trades,
        "closed_trades": row.closed_trades,
        "winning_trades": row.winning_trades,
        "winrate": row.winrate,
        "profit_factor": row.profit_factor,
        "max_drawdown_pct": row.max_drawdown_pct,
        "expectancy_r": row.expectancy_r,
        "avg_mfe_pct": row.avg_mfe_pct,
        "avg_mae_pct": row.avg_mae_pct,
        "passes_phase_gate": row.passes_phase_gate,
        "verdict": _verdict_from_row(row),
        "ran_at": row.ran_at.isoformat() if row.ran_at else None,
    }


def _trade_to_dict(row: BacktestTradeRecord) -> dict:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "symbol": row.symbol,
        "entry_time_ms": row.entry_time_ms,
        "entry_price": row.entry_price,
        "stop_loss": row.stop_loss,
        "take_profit": row.take_profit,
        "sl_method": row.sl_method,
        "exit_time_ms": row.exit_time_ms,
        "exit_price": row.exit_price,
        "exit_reason": row.exit_reason,
        "pnl_r": row.pnl_r,
        "mfe_pct": row.mfe_pct,
        "mae_pct": row.mae_pct,
        "signal_score": row.signal_score,
        "signal_context": row.signal_context_json,
    }


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
            self._session.add(
                BacktestTradeRecord(
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
                )
            )
        self._session.commit()

    def list_runs(
        self,
        symbol: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict:
        stmt = select(BacktestRun).order_by(BacktestRun.ran_at.desc())
        if symbol is not None:
            stmt = stmt.where(BacktestRun.symbol == symbol)
        if cursor is not None:
            try:
                cursor_dt = datetime.fromisoformat(cursor).replace(tzinfo=timezone.utc)
                stmt = stmt.where(BacktestRun.ran_at < cursor_dt)
            except ValueError:
                pass
        stmt = stmt.limit(limit + 1)
        rows = self._session.execute(stmt).scalars().all()
        has_more = len(rows) > limit
        items = [_run_to_dict(r) for r in rows[:limit]]
        next_cursor: str | None = None
        if has_more and items:
            next_cursor = items[-1]["ran_at"]
        return {"items": items, "next_cursor": next_cursor}

    def get_run(self, run_id: str) -> dict | None:
        row = self._session.get(BacktestRun, run_id)
        if row is None:
            return None
        return _run_to_dict(row)

    def list_trades(
        self,
        run_id: str,
        limit: int = 50,
        cursor: int | None = None,
        result: str | None = None,
        reason: str | None = None,
    ) -> dict:
        stmt = (
            select(BacktestTradeRecord)
            .where(BacktestTradeRecord.run_id == run_id)
            .order_by(BacktestTradeRecord.id)
        )
        if cursor is not None:
            stmt = stmt.where(BacktestTradeRecord.id > cursor)
        if result is not None:
            if result == "win":
                stmt = stmt.where(
                    BacktestTradeRecord.pnl_r > 0,
                    BacktestTradeRecord.exit_reason.in_(["TP", "SL"]),
                )
            elif result == "loss":
                stmt = stmt.where(
                    BacktestTradeRecord.pnl_r <= 0,
                    BacktestTradeRecord.exit_reason.in_(["TP", "SL"]),
                )
            elif result == "open":
                stmt = stmt.where(BacktestTradeRecord.exit_reason == "OPEN")
        if reason is not None:
            stmt = stmt.where(BacktestTradeRecord.exit_reason == reason)
        stmt = stmt.limit(limit + 1)
        rows = self._session.execute(stmt).scalars().all()
        has_more = len(rows) > limit
        items = [_trade_to_dict(r) for r in rows[:limit]]
        next_cursor: int | None = items[-1]["id"] if has_more and items else None
        return {"items": items, "next_cursor": next_cursor}

    def build_report(self, run_id: str, format: str = "json") -> dict | str | None:
        run_row = self._session.get(BacktestRun, run_id)
        if run_row is None:
            return None
        run_dict = _run_to_dict(run_row)
        trades_rows = (
            self._session.execute(
                select(BacktestTradeRecord)
                .where(BacktestTradeRecord.run_id == run_id)
                .order_by(BacktestTradeRecord.entry_time_ms)
            )
            .scalars()
            .all()
        )
        trades_list = [_trade_to_dict(r) for r in trades_rows]

        if format == "json":
            return {**run_dict, "trades": trades_list}

        lines: list[str] = [
            f"# Backtest Report — {run_dict['symbol']}",
            "",
            f"**Run ID**: {run_dict['run_id']}  ",
            f"**Period**: {run_dict['from_ms']} → {run_dict['to_ms']}  ",
            f"**Profile**: {run_dict['profile']}  ",
            f"**Ran at**: {run_dict['ran_at']}  ",
            "",
            "## Verdict",
            "",
            f"**{run_dict['verdict']}**",
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total trades | {run_dict['total_trades']} |",
            f"| Closed trades | {run_dict['closed_trades']} |",
            f"| Winning trades | {run_dict['winning_trades']} |",
            f"| Winrate | {run_dict['winrate'] * 100:.1f}% |",
            f"| Profit factor | {run_dict['profit_factor']:.2f} |",
            f"| Max drawdown | {run_dict['max_drawdown_pct']:.2f}% |",
            f"| Expectancy R | {run_dict['expectancy_r']:.3f} |",
            f"| Avg MFE | {run_dict['avg_mfe_pct']:.2f}% |",
            f"| Avg MAE | {run_dict['avg_mae_pct']:.2f}% |",
            "",
            f"## Trades ({len(trades_list)})",
            "",
            "| # | Entry time | Entry price | SL | TP | Exit reason | PnL R |",
            "|---|-----------|-------------|-----|-----|-------------|-------|",
        ]
        for i, t in enumerate(trades_list, 1):
            lines.append(
                f"| {i} | {t['entry_time_ms']} | {t['entry_price']:.4f} |"
                f" {t['stop_loss']:.4f} | {t['take_profit']:.4f} |"
                f" {t['exit_reason'] or 'OPEN'} | {t['pnl_r'] if t['pnl_r'] is not None else '-'} |"
            )
        return "\n".join(lines)
