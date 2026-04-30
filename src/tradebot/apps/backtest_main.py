from __future__ import annotations

import argparse
import dataclasses
from datetime import datetime, timezone

from tradebot.config.settings import Settings
from tradebot.infra.db.engine import create_session_factory
from tradebot.infra.db.repositories.backtest_repo_sql import BacktestRepoSql
from tradebot.services.backtesting.engine import BacktestEngine
from tradebot.services.backtesting.models import BacktestConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2 — Backtesting pipeline MTF")
    parser.add_argument("--symbol", default="BTCUSDC")
    parser.add_argument("--days", type=int, default=90, help="Lookback in days")
    parser.add_argument(
        "--k-atr",
        type=float,
        default=2.0,
        dest="k_atr",
        help="ATR multiplier for SL fallback (phase 2 calibration)",
    )
    parser.add_argument(
        "--r-multiple",
        type=float,
        default=1.5,
        dest="r_multiple",
        help="TP = entry + dist_SL × r_multiple",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip DB persistence (dry-run display only)",
    )
    args = parser.parse_args()

    settings = Settings()
    session_factory = create_session_factory(settings)

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    from_ms = now_ms - args.days * 24 * 3_600_000

    config = BacktestConfig(k_atr=args.k_atr, r_multiple=args.r_multiple)

    with session_factory() as session:
        engine = BacktestEngine(session)
        result = engine.run(args.symbol, from_ms, now_ms, config)

        if not args.no_save:
            repo = BacktestRepoSql(session)
            repo.save_result(result)

    m = result.metrics
    sep = "=" * 54
    print(f"\n{sep}")
    print(f"  Backtest  {result.symbol}  ({args.days}d)  run={result.run_id[:8]}")
    print(f"{sep}")
    print(
        f"  Config  k={config.k_atr}  R={config.r_multiple}  "
        f"SL_buf={config.sl_buffer_pct:.1%}  max_SL={config.max_sl_pct:.1%}"
    )
    print(f"{'─' * 54}")
    print(
        f"  Trades    total={m.total_trades}  closed={m.closed_trades}  "
        f"open={m.total_trades - m.closed_trades}"
    )
    print(f"  Winrate   {m.winrate:.1%}  " f"({'✓' if m.winrate > 0.5 else '✗'} >50%)")
    print(
        f"  PF        {m.profit_factor:.2f}  "
        f"({'✓' if m.profit_factor > 1.3 else '✗'} >1.3)"
    )
    print(
        f"  Drawdown  {m.max_drawdown_pct:.1f}%  "
        f"({'✓' if m.max_drawdown_pct < 15.0 else '✗'} <15%)"
    )
    print(f"  Expect.   {m.expectancy_r:+.3f} R/trade")
    print(f"  MFE/MAE   avg +{m.avg_mfe_pct:.2f}% / -{m.avg_mae_pct:.2f}%")
    print(f"{'─' * 54}")
    if m.passes_phase_gate:
        print("  GATE  ✓ PASS  →  conditions validées, prêt pour Phase 3")
    else:
        reasons = []
        if m.winrate <= 0.50:
            reasons.append(f"winrate {m.winrate:.1%} ≤ 50%")
        if m.profit_factor <= 1.3:
            reasons.append(f"PF {m.profit_factor:.2f} ≤ 1.3")
        if m.max_drawdown_pct >= 15.0:
            reasons.append(f"drawdown {m.max_drawdown_pct:.1f}% ≥ 15%")
        print(f"  GATE  ✗ FAIL  ({', '.join(reasons)})")
        print("         → ajuster conditions YAML, seuils, k, R, puis relancer")
    print(f"{sep}\n")
    if not args.no_save:
        print(f"  Résultats persistés : run_id={result.run_id}")


if __name__ == "__main__":
    main()
