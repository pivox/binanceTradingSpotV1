from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    JSON,
    Integer,
    Numeric,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Candle(Base):
    __tablename__ = "candles"

    symbol = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)
    open_time_ms = Column(BigInteger, primary_key=True)
    close_time_ms = Column(BigInteger, nullable=False)
    open = Column(Numeric, nullable=False)
    high = Column(Numeric, nullable=False)
    low = Column(Numeric, nullable=False)
    close = Column(Numeric, nullable=False)
    volume = Column(Numeric, nullable=False)
    is_partial = Column(Boolean, nullable=False, default=False)
    shard_id = Column(Integer, nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CandleCloseEvent(Base):
    __tablename__ = "candle_close_event"
    __table_args__ = (
        UniqueConstraint(
            "symbol", "timeframe", "open_time_ms", name="uq_candle_close_event"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    open_time_ms = Column(BigInteger, nullable=False)
    shard_id = Column(Integer, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class CandleGapRequest(Base):
    __tablename__ = "candle_gap_request"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    from_open_time_ms = Column(BigInteger, nullable=False)
    to_open_time_ms = Column(BigInteger, nullable=False)
    detected_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class IndicatorSnapshot(Base):
    __tablename__ = "indicator_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "close_time_ms",
            name="uq_indicator_snapshots_symbol_tf_close_time",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    close_time_ms = Column(BigInteger, nullable=False)
    computed_at_ms = Column(BigInteger, nullable=False)
    schema_version = Column(String, nullable=False, default="1.0.0")
    payload_json = Column(JSON, nullable=False)
    etag = Column(String, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class BackfillJob(Base):
    __tablename__ = "backfill_jobs"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "from_open_time_ms",
            "to_open_time_ms",
            name="uq_backfill_job_target_window",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    from_open_time_ms = Column(BigInteger, nullable=False)
    to_open_time_ms = Column(BigInteger, nullable=False)
    priority = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="PENDING")
    attempts = Column(Integer, nullable=False, default=0)
    next_retry_at_ms = Column(BigInteger, nullable=False, default=0)
    cooldown_until_ms = Column(BigInteger, nullable=False, default=0)
    last_http_status = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    last_weight_used = Column(Integer, nullable=True)
    rate_mode = Column(String, nullable=False, default="normal")
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ExchangeInfoCache(Base):
    __tablename__ = "exchange_info_cache"

    symbol = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="UNKNOWN")
    base_asset = Column(String, nullable=False, default="")
    quote_asset = Column(String, nullable=False, default="")

    price_tick_size = Column(Numeric, nullable=True)
    price_min = Column(Numeric, nullable=True)
    price_max = Column(Numeric, nullable=True)

    qty_step_size = Column(Numeric, nullable=True)
    qty_min = Column(Numeric, nullable=True)
    qty_max = Column(Numeric, nullable=True)

    min_notional = Column(Numeric, nullable=True)
    max_notional = Column(Numeric, nullable=True)

    order_types_json = Column(JSON, nullable=False, default=list)
    permissions_json = Column(JSON, nullable=False, default=list)
    filters_json = Column(JSON, nullable=False, default=list)
    payload_json = Column(JSON, nullable=False)
    fetched_at_ms = Column(BigInteger, nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
