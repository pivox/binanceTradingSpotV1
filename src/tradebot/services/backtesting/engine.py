from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from tradebot.infra.db.repositories.candle_repo_sql import CandleRepoSql
from tradebot.infra.db.repositories.snapshot_repo_sql import SnapshotRepoSql
from tradebot.services.backtesting.metrics import compute_metrics
from tradebot.services.backtesting.models import BacktestConfig, BacktestResult, BacktestTrade
from tradebot.services.backtesting.trade_simulator import compute_sl_tp, simulate_exit
from tradebot.services.mtf.validator import load_profile, validate

# 5-day extra lookback so higher-TF snapshots have context before the backtest window
_LOOKBACK_MS = 5 * 24 * 3_600_000
# Max forward window to simulate open trades (5 days)
_MAX_HOLD_MS = 5 * 24 * 3_600_000

SnapshotList = list[tuple[int, dict[str, Any]]]


def _find_as_of(entries: SnapshotList, at_ms: int) -> int | None:
    """Binary search: index of latest entry with close_time_ms <= at_ms."""
    lo, hi = 0, len(entries)
    while lo < hi:
        mid = (lo + hi) // 2
        if entries[mid][0] <= at_ms:
            lo = mid + 1
        else:
            hi = mid
    idx = lo - 1
    return idx if idx >= 0 else None


class BacktestEngine:
    def __init__(
        self,
        session: Session,
        profile_path: Path | None = None,
        *,
        _snap_repo: SnapshotRepoSql | None = None,
        _candle_repo: CandleRepoSql | None = None,
    ) -> None:
        self._profile = load_profile(profile_path)
        self._snap_repo = _snap_repo or SnapshotRepoSql(session)
        self._candle_repo = _candle_repo or CandleRepoSql(session)

    def run(
        self,
        symbol: str,
        from_ms: int,
        to_ms: int,
        config: BacktestConfig,
    ) -> BacktestResult:
        run_id = str(uuid.uuid4())
        trigger_tf = self._profile.trigger_tf
        all_tfs = list(self._profile.context_tfs.keys()) + [trigger_tf]

        snaps_by_tf: dict[str, SnapshotList] = {
            tf: self._snap_repo.fetch_range(symbol, tf, from_ms - _LOOKBACK_MS, to_ms)
            for tf in all_tfs
        }

        # Only evaluate signals within the requested window
        snaps_5m = [
            (t, p) for t, p in snaps_by_tf.get(trigger_tf, [])
            if from_ms <= t <= to_ms
        ]

        candles_5m = self._candle_repo.fetch_range(
            symbol, trigger_tf, from_ms, to_ms + _MAX_HOLD_MS
        )
        candles_sorted = candles_5m  # already ASC by open_time_ms from fetch_range

        trades: list[BacktestTrade] = []

        for close_time_ms, snap_5m in snaps_5m:
            aligned: dict[str, Any] = {trigger_tf: snap_5m}
            prev_aligned: dict[str, Any] = {}

            for tf in self._profile.context_tfs:
                idx = _find_as_of(snaps_by_tf.get(tf, []), close_time_ms)
                if idx is not None:
                    aligned[tf] = snaps_by_tf[tf][idx][1]
                    if idx > 0:
                        prev_aligned[tf] = snaps_by_tf[tf][idx - 1][1]

            idx_prev = _find_as_of(snaps_by_tf.get(trigger_tf, []), close_time_ms - 1)
            if idx_prev is not None:
                prev_aligned[trigger_tf] = snaps_by_tf[trigger_tf][idx_prev][1]

            signal = validate(symbol, aligned, self._profile, prev_aligned or None)
            if not signal.valid:
                continue

            entry_price = float(snap_5m["close_price"]) * (1.0 + config.slippage_pct)

            try:
                sl, tp, sl_method = compute_sl_tp(entry_price, snap_5m, config)
            except ValueError:
                continue

            lo, hi = 0, len(candles_sorted)
            while lo < hi:
                mid = (lo + hi) // 2
                if candles_sorted[mid].close_time_ms <= close_time_ms:
                    lo = mid + 1
                else:
                    hi = mid
            exit_time_ms, exit_price, exit_reason, mfe_pct, mae_pct = simulate_exit(
                entry_price, sl, tp, candles_sorted[lo:]
            )

            pnl_r: float | None = None
            dist_sl = entry_price - sl
            if exit_reason in ("TP", "SL") and exit_price is not None and dist_sl > 0:
                pnl_r = (exit_price - entry_price) / dist_sl

            trades.append(BacktestTrade(
                symbol=symbol,
                entry_time_ms=close_time_ms,
                entry_price=entry_price,
                stop_loss=sl,
                take_profit=tp,
                sl_method=sl_method,
                exit_time_ms=exit_time_ms,
                exit_price=exit_price,
                exit_reason=exit_reason,
                pnl_r=pnl_r,
                mfe_pct=mfe_pct,
                mae_pct=mae_pct,
                signal_score=signal.score,
                signal_context=signal.context_json,
            ))

        metrics = compute_metrics(trades, config.risk_pct)
        return BacktestResult(
            run_id=run_id,
            symbol=symbol,
            from_ms=from_ms,
            to_ms=to_ms,
            config=config,
            trades=trades,
            metrics=metrics,
        )
