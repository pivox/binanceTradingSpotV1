from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import re
from time import perf_counter

from aiohttp import web
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import structlog

from tradebot.api.chart_repository import ChartRepository
from tradebot.config.settings import Settings
from tradebot.daemon.control import DaemonControlError, DaemonController
from tradebot.infra.db.engine import create_session_factory
from tradebot.observability.logging import configure_logging

CONTROLLER_KEY = web.AppKey("controller", DaemonController)
LOGGER_KEY = web.AppKey("logger", structlog.BoundLogger)
RBAC_ENABLED_KEY = web.AppKey("rbac_enabled", bool)
RBAC_ADMIN_USERS_KEY = web.AppKey("rbac_admin_users", set[str])
RBAC_OPERATOR_USERS_KEY = web.AppKey("rbac_operator_users", set[str])
RBAC_STATUS_ROLES_KEY = web.AppKey("rbac_status_roles", set[str])
RBAC_USER_HEADER_KEY = web.AppKey("rbac_user_header", str)
SESSION_FACTORY_KEY = web.AppKey("session_factory", object)
CHART_MAX_LIMIT_KEY = web.AppKey("chart_max_limit", int)

SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}$")
TIMEFRAME_RE = re.compile(r"^[1-9][0-9]*[mhdwM]$")
CHART_DEFAULT_LIMIT = 500
SLOW_REQUEST_THRESHOLD_MS = 2_000


def _error_status(code: str) -> int:
    if code in {"already_running", "already_stopped"}:
        return 409
    if code == "process_not_found":
        return 404
    if code == "permission_denied":
        return 403
    return 500


def _json_ok(data: object) -> web.Response:
    return web.json_response({"ok": True, "data": data})


def _json_err(code: str, message: str, *, status: int | None = None) -> web.Response:
    return web.json_response(
        {"ok": False, "error": {"code": code, "message": message}},
        status=status or _error_status(code),
    )


def _user_from_request(request: web.Request) -> str:
    header = request.app[RBAC_USER_HEADER_KEY]
    return request.headers.get(header, "").strip() or "unknown"


def _csv_set(raw: str) -> set[str]:
    return {v.strip() for v in raw.split(",") if v.strip()}


def _roles_for_user(user: str, request: web.Request) -> set[str]:
    admins = request.app[RBAC_ADMIN_USERS_KEY]
    operators = request.app[RBAC_OPERATOR_USERS_KEY]
    roles: set[str] = set()
    if user in admins:
        roles.add("admin")
    if user in operators:
        roles.add("operator")
    return roles


def _is_allowed(action: str, roles: set[str], request: web.Request) -> bool:
    if not request.app[RBAC_ENABLED_KEY]:
        return True
    if action in {"start", "stop"}:
        return bool(roles & {"admin", "operator"})
    if action == "status":
        return bool(roles & request.app[RBAC_STATUS_ROLES_KEY])
    return False


def _is_valid_symbol(symbol: str) -> bool:
    return bool(SYMBOL_RE.fullmatch(symbol))


def _is_valid_timeframe(timeframe: str) -> bool:
    return bool(TIMEFRAME_RE.fullmatch(timeframe))


def _parse_limit(
    raw_value: str | None, max_limit: int
) -> tuple[int | None, str | None]:
    if raw_value is None:
        return CHART_DEFAULT_LIMIT, None

    value = raw_value.strip()
    if not value:
        return None, "query param 'limit' must be a positive integer"

    try:
        parsed = int(value)
    except ValueError:
        return None, "query param 'limit' must be a positive integer"

    if parsed <= 0:
        return None, "query param 'limit' must be > 0"
    if parsed > max_limit:
        return None, f"query param 'limit' must be <= {max_limit}"
    return parsed, None


def _parse_from_open_time_ms(raw_value: str | None) -> tuple[int | None, str | None]:
    if raw_value is None:
        return None, None

    value = raw_value.strip()
    if not value:
        return None, "query param 'from_open_time_ms' must be a non-negative integer"

    try:
        parsed = int(value)
    except ValueError:
        return None, "query param 'from_open_time_ms' must be a non-negative integer"

    if parsed < 0:
        return None, "query param 'from_open_time_ms' must be a non-negative integer"
    return parsed, None


@contextmanager
def _session_scope(request: web.Request) -> Iterator[Session]:
    session_factory = request.app[SESSION_FACTORY_KEY]
    if session_factory is None:
        raise RuntimeError("database session factory is unavailable")

    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _log_chart_latency(
    logger: structlog.BoundLogger,
    endpoint: str,
    started_at: float,
    *,
    result: str,
) -> None:
    duration_ms = int((perf_counter() - started_at) * 1_000)
    event_name = "chart_request"
    payload = {"endpoint": endpoint, "duration_ms": duration_ms, "result": result}
    if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
        logger.warning(event_name, **payload)
        return
    logger.info(event_name, **payload)


def create_app(settings: Settings) -> web.Application:
    configure_logging()
    logger = structlog.get_logger()

    controller = DaemonController(
        pid_file=settings.daemon_pid_file,
        command=DaemonController.command_from_env(settings.daemon_command),
        start_grace_s=settings.daemon_start_grace_s,
        stop_timeout_s=settings.daemon_stop_timeout_s,
        env_overrides={
            "DATABASE_URL": settings.database_url,
            "BINANCE_API_KEY": settings.binance_api_key,
            "BINANCE_API_SECRET": settings.binance_api_secret,
            "SHARD_COUNT": str(settings.shard_count),
        },
    )

    app = web.Application()
    app[CONTROLLER_KEY] = controller
    app[LOGGER_KEY] = logger
    session_factory = None
    try:
        session_factory = create_session_factory(settings)
    except Exception as exc:  # pragma: no cover - defensive guard for env/bootstrap
        logger.error("chart_db_bootstrap_error", error=str(exc))
    app[SESSION_FACTORY_KEY] = session_factory
    app[CHART_MAX_LIMIT_KEY] = settings.chart_max_limit
    app[RBAC_ENABLED_KEY] = settings.rbac_enabled
    app[RBAC_ADMIN_USERS_KEY] = _csv_set(settings.rbac_admin_users)
    app[RBAC_OPERATOR_USERS_KEY] = _csv_set(settings.rbac_operator_users)
    app[RBAC_STATUS_ROLES_KEY] = _csv_set(settings.rbac_status_roles)
    app[RBAC_USER_HEADER_KEY] = settings.rbac_user_header

    async def status_handler(request: web.Request) -> web.Response:
        ctrl: DaemonController = request.app[CONTROLLER_KEY]
        log = request.app[LOGGER_KEY]
        user = _user_from_request(request)
        roles = _roles_for_user(user, request)

        if not _is_allowed("status", roles, request):
            log.info(
                "daemon_status",
                user=user,
                remote=request.remote,
                result="denied",
                endpoint="/daemon/status",
            )
            return _json_err("permission_denied", "user not authorized")

        try:
            st = ctrl.status()
        except DaemonControlError as exc:
            log.info(
                "daemon_status",
                user=user,
                remote=request.remote,
                result="error",
                code=exc.code,
            )
            return _json_err(exc.code, exc.message)
        log.info(
            "daemon_status",
            user=user,
            remote=request.remote,
            status=st.status,
            pid=st.pid,
        )
        return _json_ok({"status": st.status, "pid": st.pid})

    async def start_handler(request: web.Request) -> web.Response:
        ctrl: DaemonController = request.app[CONTROLLER_KEY]
        log = request.app[LOGGER_KEY]
        user = _user_from_request(request)
        roles = _roles_for_user(user, request)

        if not _is_allowed("start", roles, request):
            log.info(
                "daemon_start",
                user=user,
                remote=request.remote,
                result="denied",
                endpoint="/daemon/start",
            )
            return _json_err("permission_denied", "user not authorized")

        try:
            st = ctrl.start()
        except DaemonControlError as exc:
            log.info(
                "daemon_start",
                user=user,
                remote=request.remote,
                result="error",
                code=exc.code,
            )
            return _json_err(exc.code, exc.message)

        log.info(
            "daemon_start",
            user=user,
            remote=request.remote,
            result="success",
            pid=st.pid,
        )
        return _json_ok({"status": st.status, "pid": st.pid})

    async def stop_handler(request: web.Request) -> web.Response:
        ctrl: DaemonController = request.app[CONTROLLER_KEY]
        log = request.app[LOGGER_KEY]
        user = _user_from_request(request)
        roles = _roles_for_user(user, request)

        if not _is_allowed("stop", roles, request):
            log.info(
                "daemon_stop",
                user=user,
                remote=request.remote,
                result="denied",
                endpoint="/daemon/stop",
            )
            return _json_err("permission_denied", "user not authorized")

        try:
            st = ctrl.stop()
        except DaemonControlError as exc:
            log.info(
                "daemon_stop",
                user=user,
                remote=request.remote,
                result="error",
                code=exc.code,
            )
            return _json_err(exc.code, exc.message)

        log.info(
            "daemon_stop",
            user=user,
            remote=request.remote,
            result="success",
        )
        return _json_ok({"status": st.status, "pid": st.pid})

    async def chart_symbols_handler(request: web.Request) -> web.Response:
        log = request.app[LOGGER_KEY]
        started_at = perf_counter()
        result = "success"
        try:
            with _session_scope(request) as session:
                symbols = ChartRepository(session).list_symbols()
        except RuntimeError as exc:
            result = "service_unavailable"
            log.error(
                "chart_symbols_error",
                endpoint="/chart/symbols",
                result=result,
                error=str(exc),
            )
            return _json_err(
                "service_unavailable",
                "database session is unavailable",
                status=503,
            )
        except SQLAlchemyError:
            result = "db_error"
            log.exception(
                "chart_symbols_error", endpoint="/chart/symbols", result=result
            )
            return _json_err("db_error", "failed to load symbols from database")
        finally:
            _log_chart_latency(log, "/chart/symbols", started_at, result=result)
        return _json_ok(symbols)

    async def chart_timeframes_handler(request: web.Request) -> web.Response:
        log = request.app[LOGGER_KEY]
        started_at = perf_counter()
        result = "success"
        raw_symbol = request.query.get("symbol")
        symbol: str | None = None

        if raw_symbol is not None:
            symbol = raw_symbol.strip().upper()
            if not symbol or not _is_valid_symbol(symbol):
                result = "invalid_request"
                _log_chart_latency(log, "/chart/timeframes", started_at, result=result)
                return _json_err(
                    "invalid_request",
                    "query param 'symbol' must match ^[A-Z0-9]{2,20}$",
                    status=400,
                )

        try:
            with _session_scope(request) as session:
                timeframes = ChartRepository(session).list_timeframes(symbol)
        except RuntimeError as exc:
            result = "service_unavailable"
            log.error(
                "chart_timeframes_error",
                endpoint="/chart/timeframes",
                result=result,
                error=str(exc),
            )
            return _json_err(
                "service_unavailable",
                "database session is unavailable",
                status=503,
            )
        except SQLAlchemyError:
            result = "db_error"
            log.exception(
                "chart_timeframes_error", endpoint="/chart/timeframes", result=result
            )
            return _json_err("db_error", "failed to load timeframes from database")
        finally:
            _log_chart_latency(log, "/chart/timeframes", started_at, result=result)
        return _json_ok(timeframes)

    async def chart_candles_handler(request: web.Request) -> web.Response:
        log = request.app[LOGGER_KEY]
        started_at = perf_counter()
        result = "success"

        raw_symbol = request.query.get("symbol")
        symbol = (raw_symbol or "").strip().upper()
        if not symbol or not _is_valid_symbol(symbol):
            result = "invalid_request"
            _log_chart_latency(log, "/chart/candles", started_at, result=result)
            return _json_err(
                "invalid_request",
                "query param 'symbol' is required and must match ^[A-Z0-9]{2,20}$",
                status=400,
            )

        raw_timeframe = request.query.get("timeframe")
        timeframe = (raw_timeframe or "").strip()
        if not timeframe or not _is_valid_timeframe(timeframe):
            result = "invalid_request"
            _log_chart_latency(log, "/chart/candles", started_at, result=result)
            return _json_err(
                "invalid_request",
                "query param 'timeframe' is required and must match ^[1-9][0-9]*[mhdwM]$",
                status=400,
            )

        max_limit = request.app[CHART_MAX_LIMIT_KEY]
        limit, limit_error = _parse_limit(request.query.get("limit"), max_limit)
        if limit_error:
            result = "invalid_request"
            _log_chart_latency(log, "/chart/candles", started_at, result=result)
            return _json_err("invalid_request", limit_error, status=400)

        from_open_time_ms, from_open_error = _parse_from_open_time_ms(
            request.query.get("from_open_time_ms")
        )
        if from_open_error:
            result = "invalid_request"
            _log_chart_latency(log, "/chart/candles", started_at, result=result)
            return _json_err("invalid_request", from_open_error, status=400)

        try:
            with _session_scope(request) as session:
                candles = ChartRepository(session).fetch_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit or CHART_DEFAULT_LIMIT,
                    from_open_time_ms=from_open_time_ms,
                )
        except RuntimeError as exc:
            result = "service_unavailable"
            log.error(
                "chart_candles_error",
                endpoint="/chart/candles",
                result=result,
                error=str(exc),
            )
            return _json_err(
                "service_unavailable",
                "database session is unavailable",
                status=503,
            )
        except SQLAlchemyError:
            result = "db_error"
            log.exception(
                "chart_candles_error", endpoint="/chart/candles", result=result
            )
            return _json_err("db_error", "failed to load candles from database")
        finally:
            _log_chart_latency(log, "/chart/candles", started_at, result=result)
        return _json_ok(candles)

    app.router.add_get("/daemon/status", status_handler)
    app.router.add_post("/daemon/start", start_handler)
    app.router.add_post("/daemon/stop", stop_handler)
    app.router.add_get("/chart/symbols", chart_symbols_handler)
    app.router.add_get("/chart/timeframes", chart_timeframes_handler)
    app.router.add_get("/chart/candles", chart_candles_handler)
    static_dir = Path(__file__).parent / "static"

    async def index_handler(_request: web.Request) -> web.FileResponse:
        return web.FileResponse(static_dir / "index.html")

    async def chart_handler(_request: web.Request) -> web.FileResponse:
        return web.FileResponse(static_dir / "chart.html")

    app.router.add_get("/", index_handler)
    app.router.add_get("/chart", chart_handler)
    app.router.add_static("/static/", static_dir)
    return app
