import logging

import structlog

_LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def resolve_log_level(raw_level: str | None, *, default: str = "INFO") -> int:
    level_name = (raw_level or "").strip().upper() or default
    if level_name not in _LOG_LEVELS:
        allowed = ", ".join(_LOG_LEVELS.keys())
        raise ValueError(f"Invalid log level: {raw_level!r}. Allowed values: {allowed}")
    return _LOG_LEVELS[level_name]


def configure_logging(*, level: str = "INFO") -> None:
    level_no = resolve_log_level(level)
    logging.basicConfig(level=level_no, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", force=True)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
