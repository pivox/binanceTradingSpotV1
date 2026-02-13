from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradebot.api.chart_repository import ChartRepository
from tradebot.infra.db.models import Base, Candle


def _session_factory(db_url: str):
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _seed(session) -> None:
    session.add_all(
        [
            Candle(
                symbol="ETHUSDC",
                timeframe="5m",
                open_time_ms=1_000,
                close_time_ms=1_999,
                open=Decimal("200"),
                high=Decimal("201"),
                low=Decimal("199"),
                close=Decimal("200.5"),
                volume=Decimal("20"),
                is_partial=False,
                shard_id=1,
            ),
            Candle(
                symbol="BTCUSDC",
                timeframe="1m",
                open_time_ms=1_000,
                close_time_ms=1_999,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.5"),
                volume=Decimal("10"),
                is_partial=False,
                shard_id=1,
            ),
            Candle(
                symbol="BTCUSDC",
                timeframe="1m",
                open_time_ms=2_000,
                close_time_ms=2_999,
                open=Decimal("101"),
                high=Decimal("102"),
                low=Decimal("100"),
                close=Decimal("101.5"),
                volume=Decimal("11"),
                is_partial=False,
                shard_id=1,
            ),
            Candle(
                symbol="BTCUSDC",
                timeframe="1m",
                open_time_ms=3_000,
                close_time_ms=3_999,
                open=Decimal("102"),
                high=Decimal("103"),
                low=Decimal("101"),
                close=Decimal("102.5"),
                volume=Decimal("12"),
                is_partial=False,
                shard_id=1,
            ),
            Candle(
                symbol="BTCUSDC",
                timeframe="5m",
                open_time_ms=4_000,
                close_time_ms=4_999,
                open=Decimal("103"),
                high=Decimal("104"),
                low=Decimal("102"),
                close=Decimal("103.5"),
                volume=Decimal("13"),
                is_partial=False,
                shard_id=1,
            ),
        ]
    )
    session.commit()


def test_list_symbols_and_timeframes_sorted(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'chart_repo.db'}"
    engine, session_factory = _session_factory(db_url)
    try:
        with session_factory() as session:
            _seed(session)
            repo = ChartRepository(session)
            assert repo.list_symbols() == ["BTCUSDC", "ETHUSDC"]
            assert repo.list_timeframes() == ["1m", "5m"]
            assert repo.list_timeframes("BTCUSDC") == ["1m", "5m"]
    finally:
        engine.dispose()


def test_fetch_candles_latest_window_and_strict_from_filter(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'chart_repo.db'}"
    engine, session_factory = _session_factory(db_url)
    try:
        with session_factory() as session:
            _seed(session)
            repo = ChartRepository(session)

            latest = repo.fetch_candles(symbol="BTCUSDC", timeframe="1m", limit=2)
            assert [item["open_time_ms"] for item in latest] == [2_000, 3_000]

            incr = repo.fetch_candles(
                symbol="BTCUSDC",
                timeframe="1m",
                limit=10,
                from_open_time_ms=2_000,
            )
            assert [item["open_time_ms"] for item in incr] == [3_000]
    finally:
        engine.dispose()
