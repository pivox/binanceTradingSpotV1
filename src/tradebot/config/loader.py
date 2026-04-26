from __future__ import annotations

from pathlib import Path
from typing import List

import yaml

from tradebot.config.types import (
    AppConfig,
    ExitPlanConfig,
    LotConfig,
    LotRuleConfig,
    SchedulesConfig,
    ShardingConfig,
    StrategyConfig,
)


def load_symbols(path: Path) -> List[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def load_app_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text())

    lots = []
    for lot in raw["strategy"]["exit_plan"]["lots"]:
        rule = LotRuleConfig(
            type=lot["rule"]["type"],
            params={k: v for k, v in lot["rule"].items() if k != "type"},
        )
        lots.append(LotConfig(id=lot["id"], pct=float(lot["pct"]), rule=rule))

    strategy = StrategyConfig(
        mtf_cascade=raw["strategy"]["mtf_cascade"],
        max_open_positions=int(raw["strategy"]["max_open_positions"]),
        per_trade_quote_budget=float(raw["strategy"]["per_trade_quote_budget"]),
        exit_plan=ExitPlanConfig(lots=lots),
        daily_loss_limit_usdc=float(raw["strategy"].get("daily_loss_limit_usdc", -50.0)),
    )

    schedules = SchedulesConfig(
        candles_tick_sec=int(raw["schedules"]["candles_tick_sec"]),
        positions_tick_sec=int(raw["schedules"]["positions_tick_sec"]),
        reconcile_klines_min=int(raw["schedules"]["reconcile_klines_min"]),
        reconcile_orders_min=int(raw["schedules"]["reconcile_orders_min"]),
        exchangeinfo_daily=str(raw["schedules"]["exchangeinfo_daily"]),
    )

    sharding = ShardingConfig(shard_count=int(raw["sharding"]["shard_count"]))

    return AppConfig(
        sharding=sharding,
        timeframes=raw["timeframes"],
        schedules=schedules,
        strategy=strategy,
    )
