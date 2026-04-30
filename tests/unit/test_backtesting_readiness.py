"""Unit tests for ReadinessService."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradebot.infra.db.models import Base, Candle, IndicatorSnapshot
from tradebot.services.backtesting.readiness import ReadinessService


def _make_session(db_url: str):
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _candle(symbol, tf, open_time_ms, close_time_ms=None):
    return Candle(
        symbol=symbol,
        timeframe=tf,
        open_time_ms=open_time_ms,
        close_time_ms=close_time_ms or (open_time_ms + 59_999),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("1"),
        is_partial=False,
        shard_id=0,
    )


_TF_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
}

FROM_MS = 1_700_000_000_000
# 2 hours window → 24 5m candles, 8 15m, 2 1h, 0.5 4h
TO_MS = FROM_MS + 2 * 3_600_000


def _seed_full_coverage(session, symbol="BTCUSDC"):
    """Seed all required timeframes at full coverage inside the window."""
    candles = []
    for tf, interval in _TF_MS.items():
        t = FROM_MS
        while t < TO_MS:
            candles.append(_candle(symbol, tf, t, t + interval - 1))
            t += interval
    # Warmup: 200 5m candles before FROM_MS
    for i in range(200):
        t = FROM_MS - (i + 1) * 300_000
        candles.append(_candle(symbol, "5m", t, t + 299_999))
    session.add_all(candles)
    session.commit()


class TestReadinessServiceCoverage:
    def test_full_coverage_returns_ready(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/r.db"
        sf = _make_session(db_url)
        with sf() as s:
            _seed_full_coverage(s)
        with sf() as s:
            result = ReadinessService(s).check("BTCUSDC", FROM_MS, TO_MS)
        assert result.status == "ready"
        assert result.warmup_ok is True
        assert result.reasons == []

    def test_empty_db_returns_blocked(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/r.db"
        sf = _make_session(db_url)
        with sf() as s:
            pass  # no data
        with sf() as s:
            result = ReadinessService(s).check("BTCUSDC", FROM_MS, TO_MS)
        assert result.status == "blocked"
        for cov in result.timeframes:
            assert cov.candle_count == 0
            assert cov.status == "blocked"

    def test_coverage_pct_calculation(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/r.db"
        sf = _make_session(db_url)
        with sf() as s:
            # Seed only 50% of expected 5m candles in window
            # window = 2h = 24 5m candles expected; seed 12
            candles = []
            for i in range(12):
                t = FROM_MS + i * 300_000 * 2  # every 2 intervals → 50% coverage
                candles.append(_candle("BTCUSDC", "5m", t, t + 299_999))
            s.add_all(candles)
            s.commit()
        with sf() as s:
            result = ReadinessService(s).check("BTCUSDC", FROM_MS, TO_MS)
        cov_5m = next(c for c in result.timeframes if c.timeframe == "5m")
        # 12 candles vs 24 expected → ~50%
        assert cov_5m.coverage_pct < 70.0
        assert cov_5m.status == "blocked"

    def test_warning_band_coverage(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/r.db"
        sf = _make_session(db_url)
        with sf() as s:
            # Seed ~80% of expected 5m candles
            # 24 expected → seed 20
            candles = []
            for i in range(20):
                t = FROM_MS + i * 300_000
                candles.append(_candle("BTCUSDC", "5m", t, t + 299_999))
            s.add_all(candles)
            s.commit()
        with sf() as s:
            result = ReadinessService(s).check("BTCUSDC", FROM_MS, TO_MS)
        cov_5m = next(c for c in result.timeframes if c.timeframe == "5m")
        assert 70.0 <= cov_5m.coverage_pct < 95.0
        assert cov_5m.status == "warning"

    def test_gap_detection(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/r.db"
        sf = _make_session(db_url)
        with sf() as s:
            # Seed 5m candles with a big gap in the middle
            candles = []
            for i in range(5):
                t = FROM_MS + i * 300_000
                candles.append(_candle("BTCUSDC", "5m", t, t + 299_999))
            # skip 3 candles → gap of 4 intervals (> 1.5 * 300000)
            for i in range(9, 15):
                t = FROM_MS + i * 300_000
                candles.append(_candle("BTCUSDC", "5m", t, t + 299_999))
            s.add_all(candles)
            s.commit()
        with sf() as s:
            result = ReadinessService(s).check("BTCUSDC", FROM_MS, TO_MS)
        cov_5m = next(c for c in result.timeframes if c.timeframe == "5m")
        assert len(cov_5m.gaps) >= 1
        gap = cov_5m.gaps[0]
        assert "from_ms" in gap
        assert "to_ms" in gap
        assert "gap_ms" in gap
        assert gap["gap_ms"] > 1.5 * 300_000

    def test_warmup_insufficient(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/r.db"
        sf = _make_session(db_url)
        with sf() as s:
            # Full coverage in window but only 50 warmup candles
            _seed_full_coverage(s)
            # Remove warmup candles except 50 (they were added at negative offsets)
            from tradebot.infra.db.models import Candle as CandleModel

            # Delete all 5m candles before FROM_MS except leave 50
            all_before = (
                s.query(CandleModel)
                .filter(
                    CandleModel.symbol == "BTCUSDC",
                    CandleModel.timeframe == "5m",
                    CandleModel.open_time_ms < FROM_MS,
                )
                .order_by(CandleModel.open_time_ms.desc())
                .all()
            )
            for row in all_before[50:]:
                s.delete(row)
            s.commit()
        with sf() as s:
            result = ReadinessService(s).check("BTCUSDC", FROM_MS, TO_MS)
        assert result.warmup_ok is False
        assert any("warmup" in r.lower() for r in result.reasons)

    def test_has_snapshots_field(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/r.db"
        sf = _make_session(db_url)
        with sf() as s:
            _seed_full_coverage(s)
            snap = IndicatorSnapshot(
                symbol="BTCUSDC",
                timeframe="5m",
                close_time_ms=FROM_MS + 300_000,
                computed_at_ms=FROM_MS + 400_000,
                schema_version="1.0.0",
                payload_json={"rsi": 55.0},
                etag="abc",
            )
            s.add(snap)
            s.commit()
        with sf() as s:
            result = ReadinessService(s).check("BTCUSDC", FROM_MS, TO_MS)
        cov_5m = next(c for c in result.timeframes if c.timeframe == "5m")
        assert cov_5m.has_snapshots is True

    def test_no_snapshots_field(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/r.db"
        sf = _make_session(db_url)
        with sf() as s:
            _seed_full_coverage(s)
        with sf() as s:
            result = ReadinessService(s).check("BTCUSDC", FROM_MS, TO_MS)
        cov_5m = next(c for c in result.timeframes if c.timeframe == "5m")
        assert cov_5m.has_snapshots is False

    def test_result_fields(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/r.db"
        sf = _make_session(db_url)
        with sf() as s:
            _seed_full_coverage(s)
        with sf() as s:
            result = ReadinessService(s).check("BTCUSDC", FROM_MS, TO_MS, "myprofile")
        assert result.symbol == "BTCUSDC"
        assert result.from_ms == FROM_MS
        assert result.to_ms == TO_MS
        assert result.profile == "myprofile"
        assert len(result.timeframes) == 5
        tf_names = [c.timeframe for c in result.timeframes]
        assert "4h" in tf_names
        assert "1h" in tf_names
        assert "15m" in tf_names
        assert "5m" in tf_names
        assert "1m" in tf_names
