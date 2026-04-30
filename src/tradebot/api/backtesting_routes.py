from __future__ import annotations

import dataclasses
import re

from aiohttp import web

from tradebot.api.app import SESSION_FACTORY_KEY, _json_err, _json_ok  # type: ignore[attr-defined]
from tradebot.infra.db.repositories.backtest_repo_sql import BacktestRepoSql
from tradebot.services.backtesting.engine import BacktestEngine
from tradebot.services.backtesting.models import BacktestConfig
from tradebot.services.backtesting.readiness import ReadinessService

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}$")
_MS_365_DAYS = 365 * 24 * 3_600_000


def _is_valid_symbol(symbol: str) -> bool:
    return bool(_SYMBOL_RE.fullmatch(symbol))


def _readiness_tf_to_dict(cov) -> dict:
    return {
        "timeframe": cov.timeframe,
        "candle_count": cov.candle_count,
        "first_ms": cov.first_ms,
        "last_ms": cov.last_ms,
        "coverage_pct": round(cov.coverage_pct, 2),
        "gaps": cov.gaps,
        "has_snapshots": cov.has_snapshots,
        "status": cov.status,
    }


async def readiness_handler(request: web.Request) -> web.Response:
    symbol = request.rel_url.query.get("symbol", "").strip()
    if not symbol or not _is_valid_symbol(symbol):
        return _json_err(
            "invalid_param", "symbol must match ^[A-Z0-9]{2,20}$", status=400
        )

    raw_from = request.rel_url.query.get("from_ms", "").strip()
    raw_to = request.rel_url.query.get("to_ms", "").strip()
    if not raw_from or not raw_to:
        return _json_err("invalid_param", "from_ms and to_ms are required", status=400)
    try:
        from_ms = int(raw_from)
        to_ms = int(raw_to)
    except ValueError:
        return _json_err(
            "invalid_param", "from_ms and to_ms must be integers", status=400
        )
    if from_ms <= 0 or to_ms <= 0:
        return _json_err(
            "invalid_param", "from_ms and to_ms must be positive", status=400
        )
    if from_ms >= to_ms:
        return _json_err("invalid_param", "from_ms must be < to_ms", status=400)
    if (to_ms - from_ms) > _MS_365_DAYS:
        return _json_err(
            "invalid_param", "date range must not exceed 365 days", status=400
        )

    profile = request.rel_url.query.get("profile", "regular").strip() or "regular"

    session_factory = request.app[SESSION_FACTORY_KEY]
    with session_factory() as session:
        svc = ReadinessService(session)
        result = svc.check(symbol, from_ms, to_ms, profile)

    return _json_ok(
        {
            "symbol": result.symbol,
            "from_ms": result.from_ms,
            "to_ms": result.to_ms,
            "profile": result.profile,
            "timeframes": [_readiness_tf_to_dict(c) for c in result.timeframes],
            "warmup_ok": result.warmup_ok,
            "status": result.status,
            "reasons": result.reasons,
        }
    )


async def create_run_handler(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return _json_err("invalid_body", "request body must be valid JSON", status=400)

    symbol = str(body.get("symbol", "")).strip()
    if not symbol or not _is_valid_symbol(symbol):
        return _json_err(
            "invalid_param", "symbol must match ^[A-Z0-9]{2,20}$", status=400
        )

    raw_from = body.get("from_ms")
    raw_to = body.get("to_ms")
    if raw_from is None or raw_to is None:
        return _json_err("invalid_param", "from_ms and to_ms are required", status=400)
    try:
        from_ms = int(raw_from)
        to_ms = int(raw_to)
    except (TypeError, ValueError):
        return _json_err(
            "invalid_param", "from_ms and to_ms must be integers", status=400
        )
    if from_ms <= 0 or to_ms <= 0:
        return _json_err(
            "invalid_param", "from_ms and to_ms must be positive", status=400
        )
    if from_ms >= to_ms:
        return _json_err("invalid_param", "from_ms must be < to_ms", status=400)
    if (to_ms - from_ms) > _MS_365_DAYS:
        return _json_err(
            "invalid_param", "date range must not exceed 365 days", status=400
        )

    cfg_raw = body.get("config", {}) or {}
    try:
        config = BacktestConfig(
            profile=str(cfg_raw.get("profile", "regular")),
            slippage_pct=float(cfg_raw.get("slippage_pct", 0.0005)),
            k_atr=float(cfg_raw.get("k_atr", 2.0)),
            r_multiple=float(cfg_raw.get("r_multiple", 1.5)),
            sl_buffer_pct=float(cfg_raw.get("sl_buffer_pct", 0.003)),
            max_sl_pct=float(cfg_raw.get("max_sl_pct", 0.02)),
            risk_pct=float(cfg_raw.get("risk_pct", 0.01)),
            initial_capital_usdc=float(cfg_raw.get("initial_capital_usdc", 10000.0)),
            fees_pct=float(cfg_raw.get("fees_pct", 0.001)),
            min_closed_trades=int(cfg_raw.get("min_closed_trades", 20)),
            mode=str(cfg_raw.get("mode", "exploration")),  # type: ignore[arg-type]
        )
    except (TypeError, ValueError) as exc:
        return _json_err("invalid_param", f"invalid config: {exc}", status=400)

    session_factory = request.app[SESSION_FACTORY_KEY]
    with session_factory() as session:
        engine = BacktestEngine(session, profile_path=None)
        result = engine.run(symbol, from_ms, to_ms, config)
        repo = BacktestRepoSql(session)
        repo.save_result(result)

    m = result.metrics
    return _json_ok(
        {
            "run_id": result.run_id,
            "symbol": result.symbol,
            "from_ms": result.from_ms,
            "to_ms": result.to_ms,
            "config": dataclasses.asdict(result.config),
            "metrics": {
                "total_trades": m.total_trades,
                "closed_trades": m.closed_trades,
                "winning_trades": m.winning_trades,
                "winrate": m.winrate,
                "profit_factor": m.profit_factor,
                "max_drawdown_pct": m.max_drawdown_pct,
                "expectancy_r": m.expectancy_r,
                "avg_mfe_pct": m.avg_mfe_pct,
                "avg_mae_pct": m.avg_mae_pct,
                "passes_phase_gate": m.passes_phase_gate,
                "verdict": m.verdict.value,
                "verdict_reasons": m.verdict_reasons,
            },
        }
    )


async def list_runs_handler(request: web.Request) -> web.Response:
    symbol_raw = request.rel_url.query.get("symbol", "").strip() or None
    if symbol_raw is not None and not _is_valid_symbol(symbol_raw):
        return _json_err(
            "invalid_param", "symbol must match ^[A-Z0-9]{2,20}$", status=400
        )

    raw_limit = request.rel_url.query.get("limit", "20").strip()
    try:
        limit = int(raw_limit)
    except ValueError:
        return _json_err("invalid_param", "limit must be an integer", status=400)
    if limit < 1 or limit > 100:
        return _json_err("invalid_param", "limit must be between 1 and 100", status=400)

    cursor = request.rel_url.query.get("cursor", "").strip() or None

    session_factory = request.app[SESSION_FACTORY_KEY]
    with session_factory() as session:
        repo = BacktestRepoSql(session)
        data = repo.list_runs(symbol=symbol_raw, limit=limit, cursor=cursor)

    return _json_ok(data)


async def get_run_handler(request: web.Request) -> web.Response:
    run_id = request.match_info["run_id"]

    session_factory = request.app[SESSION_FACTORY_KEY]
    with session_factory() as session:
        repo = BacktestRepoSql(session)
        data = repo.get_run(run_id)

    if data is None:
        return _json_err("not_found", f"run {run_id} not found", status=404)
    return _json_ok(data)


async def list_trades_handler(request: web.Request) -> web.Response:
    run_id = request.match_info["run_id"]

    raw_limit = request.rel_url.query.get("limit", "50").strip()
    try:
        limit = int(raw_limit)
    except ValueError:
        return _json_err("invalid_param", "limit must be an integer", status=400)
    if limit < 1 or limit > 100:
        return _json_err("invalid_param", "limit must be between 1 and 100", status=400)

    raw_cursor = request.rel_url.query.get("cursor", "").strip() or None
    cursor: int | None = None
    if raw_cursor is not None:
        try:
            cursor = int(raw_cursor)
        except ValueError:
            return _json_err("invalid_param", "cursor must be an integer", status=400)

    result_filter = request.rel_url.query.get("result", "").strip() or None
    if result_filter is not None and result_filter not in {"win", "loss", "open"}:
        return _json_err(
            "invalid_param", "result must be one of: win, loss, open", status=400
        )

    reason_filter = request.rel_url.query.get("reason", "").strip() or None
    if reason_filter is not None and reason_filter not in {"TP", "SL", "OPEN"}:
        return _json_err(
            "invalid_param", "reason must be one of: TP, SL, OPEN", status=400
        )

    session_factory = request.app[SESSION_FACTORY_KEY]
    with session_factory() as session:
        repo = BacktestRepoSql(session)
        data = repo.list_trades(
            run_id=run_id,
            limit=limit,
            cursor=cursor,
            result=result_filter,
            reason=reason_filter,
        )

    return _json_ok(data)


async def get_report_handler(request: web.Request) -> web.Response:
    run_id = request.match_info["run_id"]

    fmt = request.rel_url.query.get("format", "json").strip() or "json"
    if fmt not in {"json", "markdown"}:
        return _json_err(
            "invalid_param", "format must be one of: json, markdown", status=400
        )

    session_factory = request.app[SESSION_FACTORY_KEY]
    with session_factory() as session:
        repo = BacktestRepoSql(session)
        data = repo.build_report(run_id=run_id, format=fmt)

    if data is None:
        return _json_err("not_found", f"run {run_id} not found", status=404)

    if fmt == "markdown":
        return web.Response(text=str(data), content_type="text/markdown")
    return _json_ok(data)


def register_backtesting_routes(app: web.Application) -> None:
    app.router.add_get("/backtesting/readiness", readiness_handler)
    app.router.add_post("/backtesting/runs", create_run_handler)
    app.router.add_get("/backtesting/runs", list_runs_handler)
    app.router.add_get("/backtesting/runs/{run_id}", get_run_handler)
    app.router.add_get("/backtesting/runs/{run_id}/trades", list_trades_handler)
    app.router.add_get("/backtesting/runs/{run_id}/report", get_report_handler)
