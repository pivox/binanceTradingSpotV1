from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Integer,
    Numeric,
    String,
    TIMESTAMP,
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
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
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
