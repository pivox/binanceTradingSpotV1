from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    Index,
    JSON,
    Integer,
    Numeric,
    SmallInteger,
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


class CandleCloseEventProcessed(Base):
    """Tracks processed_at for candle close events (pipeline activity T-0051)."""
    __tablename__ = "candle_close_event_processed"

    id = Column(BigInteger, primary_key=True)  # FK to candle_close_event.id
    processed_at_ms = Column(BigInteger, nullable=False)


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        Index("ix_positions_shard_status_checked", "shard_id", "status", "last_checked_ms"),
        Index("ix_positions_symbol_status", "symbol", "status"),
    )

    id = Column(String(36), primary_key=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(4), nullable=False)
    status = Column(String(20), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    quantity_total = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=False)
    atr_at_entry = Column(Numeric(20, 8), nullable=False)
    signal_score = Column(Float, nullable=False)
    setup_type = Column(String(1), nullable=False)
    shard_id = Column(SmallInteger, nullable=False)
    opened_at_ms = Column(BigInteger, nullable=False)
    closed_at_ms = Column(BigInteger, nullable=True)
    exit_plan_json = Column(Text, nullable=False)
    high_since_entry = Column(Numeric(20, 8), nullable=False)
    last_checked_ms = Column(BigInteger, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OrderIntent(Base):
    __tablename__ = "order_intents"
    __table_args__ = (
        UniqueConstraint("intent_key", name="uq_order_intents_intent_key"),
        Index("ix_order_intents_symbol_status", "symbol", "status"),
        Index("ix_order_intents_position", "position_id"),
    )

    id = Column(String(36), primary_key=True)
    intent_key = Column(String(128), nullable=False)
    position_id = Column(String(36), nullable=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(4), nullable=False)
    order_type = Column(String(20), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=True)
    stop_price = Column(Numeric(20, 8), nullable=True)
    lot_id = Column(String(4), nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")
    binance_order_id = Column(BigInteger, nullable=True)
    filled_qty = Column(Numeric(20, 8), nullable=True)
    avg_price = Column(Numeric(20, 8), nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at_ms = Column(BigInteger, nullable=False)
    updated_at_ms = Column(BigInteger, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class MtfState(Base):
    __tablename__ = "mtf_states"

    symbol = Column(String(20), primary_key=True)
    regime = Column(String(20), nullable=False)
    cascade_passed = Column(Boolean, nullable=False)
    score = Column(Float, nullable=False)
    quality = Column(String(10), nullable=False)
    active_setup = Column(String(1), nullable=True)
    scores_by_tf_json = Column(Text, nullable=False)
    rejection_reason = Column(Text, nullable=True)
    evaluated_at_ms = Column(BigInteger, nullable=False)
    signal_open_time_ms = Column(BigInteger, nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MtfSignalRecord(Base):
    __tablename__ = "mtf_signals"
    __table_args__ = (
        Index("ix_mtf_signals_symbol_eval", "symbol", "evaluated_at_ms"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    profile = Column(String(50), nullable=False)
    trend_4h = Column(Boolean, nullable=False)
    trend_1h = Column(Boolean, nullable=False)
    structure_15m = Column(Boolean, nullable=False)
    trigger_5m = Column(Boolean, nullable=False)
    score = Column(Integer, nullable=False)
    valid = Column(Boolean, nullable=False)
    blocking_filter = Column(String(100), nullable=True)
    context_json = Column(JSON, nullable=False)
    evaluated_at_ms = Column(BigInteger, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class PnlTrade(Base):
    __tablename__ = "pnl_trades"
    __table_args__ = (
        Index("ix_pnl_trades_closed_at", "closed_at_ms"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    position_id = Column(String(36), nullable=False, unique=True)
    symbol = Column(String(20), nullable=False)
    opened_at_ms = Column(BigInteger, nullable=False)
    closed_at_ms = Column(BigInteger, nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    exit_price_avg = Column(Numeric(20, 8), nullable=False)
    quantity_total = Column(Numeric(20, 8), nullable=False)
    realized_pnl = Column(Numeric(20, 8), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


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
