from __future__ import annotations

import asyncio

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from tradebot.infra.db.models import BackfillJob, Base, Candle, CandleGapRequest
from tradebot.temporal_app import activities as act


def _session_factory(db_url: str):
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_reconcile_klines_backfills_gap_requests(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'reconcile_klines_ok.db'}"
    engine, sf = _session_factory(db_url)
    try:
        with sf() as session:
            session.add(
                CandleGapRequest(
                    symbol="BTCUSDC",
                    from_open_time_ms=120_000,
                    to_open_time_ms=180_000,
                )
            )
            session.commit()

        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("SHARD_COUNT", "8")

        async def _fake_fetch(
            _http_session,
            *,
            base_url: str,
            symbol: str,
            timeframe: str,
            start_time_ms: int,
            end_time_ms: int,
        ) -> act._HttpResult:
            del base_url, end_time_ms
            assert symbol == "BTCUSDC"
            assert timeframe == "1m"
            assert start_time_ms == 120_000
            return act._HttpResult(
                status=200,
                headers={"X-MBX-USED-WEIGHT-1M": "12"},
                payload=[
                    [120_000, "1.0", "2.0", "0.5", "1.5", "10.0", 179_999],
                ],
            )

        monkeypatch.setattr(act, "_fetch_binance_klines_batch", _fake_fetch)

        out = asyncio.run(act.reconcile_klines())
        assert out["ok"] is True
        assert out["gap_requests"] == 1
        assert out["jobs_processed"] == 1
        assert out["gaps_filled"] == 1

        with sf() as session:
            candle = session.scalar(
                select(Candle).where(
                    Candle.symbol == "BTCUSDC",
                    Candle.timeframe == "1m",
                    Candle.open_time_ms == 120_000,
                )
            )
            assert candle is not None
            assert float(candle.close) == 1.5

            jobs = list(session.scalars(select(BackfillJob)))
            assert len(jobs) == 1
            assert jobs[0].status == "DONE"

            gap_requests = list(session.scalars(select(CandleGapRequest)))
            assert gap_requests == []
    finally:
        engine.dispose()


def test_reconcile_klines_records_retry_when_binance_rate_limits(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'reconcile_klines_retry.db'}"
    engine, sf = _session_factory(db_url)
    try:
        with sf() as session:
            session.add(
                CandleGapRequest(
                    symbol="BTCUSDC",
                    from_open_time_ms=120_000,
                    to_open_time_ms=180_000,
                )
            )
            session.commit()

        monkeypatch.setenv("DATABASE_URL", db_url)
        monkeypatch.setenv("SHARD_COUNT", "8")

        async def _fake_fetch(
            _http_session,
            *,
            base_url: str,
            symbol: str,
            timeframe: str,
            start_time_ms: int,
            end_time_ms: int,
        ) -> act._HttpResult:
            del base_url, symbol, timeframe, start_time_ms, end_time_ms
            raise act._BinanceHttpError(
                429,
                {"X-MBX-USED-WEIGHT-1M": "1100"},
                "rate limited",
            )

        monkeypatch.setattr(act, "_fetch_binance_klines_batch", _fake_fetch)

        out = asyncio.run(act.reconcile_klines())
        assert out["ok"] is False
        assert out["gap_requests"] == 1
        assert out["jobs_processed"] == 1
        assert out["failures"] == 1

        with sf() as session:
            jobs = list(session.scalars(select(BackfillJob)))
            assert len(jobs) == 1
            assert jobs[0].status in {"RETRY_WAIT", "COOLDOWN"}
    finally:
        engine.dispose()
