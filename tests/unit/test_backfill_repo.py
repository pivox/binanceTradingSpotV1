from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradebot.infra.db.models import BackfillJob, Base, Candle
from tradebot.infra.db.repositories.backfill_repo_sql import (
    BackfillRepoSql,
    BackfillRetryPolicy,
)


def _session_factory(db_url: str):
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _seed_candles(session) -> None:
    session.add_all(
        [
            Candle(
                symbol="BTCUSDC",
                timeframe="1m",
                open_time_ms=0,
                close_time_ms=59_999,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("10"),
                is_partial=False,
                shard_id=1,
            ),
            Candle(
                symbol="BTCUSDC",
                timeframe="1m",
                open_time_ms=60_000,
                close_time_ms=119_999,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("10"),
                is_partial=False,
                shard_id=1,
            ),
            Candle(
                symbol="BTCUSDC",
                timeframe="1m",
                open_time_ms=180_000,
                close_time_ms=239_999,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("10"),
                is_partial=False,
                shard_id=1,
            ),
        ]
    )
    session.commit()


def test_detect_gaps_and_schedule_jobs(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'backfill.db'}"
    engine, session_factory = _session_factory(db_url)
    try:
        with session_factory() as session:
            _seed_candles(session)
            repo = BackfillRepoSql(session)
            gaps = repo.detect_gaps(
                symbol="BTCUSDC",
                timeframe="1m",
                from_open_time_ms=0,
                to_open_time_ms=240_000,
            )
            assert gaps == [(120_000, 120_000), (240_000, 240_000)]

            created = repo.schedule_gap_jobs(
                symbol="BTCUSDC",
                timeframe="1m",
                gaps=gaps,
                priority=10,
                now_ms=1_000,
            )
            assert len(created) == 2
            assert all(job.status == "PENDING" for job in created)

            duplicate = repo.schedule_gap_jobs(
                symbol="BTCUSDC",
                timeframe="1m",
                gaps=gaps,
                priority=10,
                now_ms=1_000,
            )
            assert duplicate == []
    finally:
        engine.dispose()


def test_429_retry_and_418_cooldown_policies(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'backfill.db'}"
    engine, session_factory = _session_factory(db_url)
    try:
        with session_factory() as session:
            repo = BackfillRepoSql(session)
            jobs = repo.schedule_gap_jobs(
                symbol="BTCUSDC",
                timeframe="1m",
                gaps=[(120_000, 120_000)],
                priority=20,
                now_ms=100,
            )
            job_id = int(jobs[0].id)
            policy = BackfillRetryPolicy(
                max_attempts=3,
                base_backoff_ms=100,
                max_backoff_ms=1_000,
                max_retry_window_ms=10_000,
                cooldown_ms=5_000,
                weight_limit_1m=1200,
                slow_mode_threshold_ratio=0.8,
            )

            event = repo.record_http_result(
                job_id=job_id,
                http_status=429,
                now_ms=1_000,
                headers={"X-MBX-USED-WEIGHT-1M": "1100"},
                policy=policy,
            )
            session.expire_all()
            job = session.get(BackfillJob, job_id)
            assert event["event"] == "backfill_retry_scheduled"
            assert event["rate_mode"] == "slow"
            assert job is not None
            assert job.status == "RETRY_WAIT"
            assert job.attempts == 1
            assert job.next_retry_at_ms > 1_000

            event = repo.record_http_result(
                job_id=job_id,
                http_status=418,
                now_ms=2_000,
                headers={"X-MBX-USED-WEIGHT-1M": "500"},
                policy=policy,
            )
            session.expire_all()
            job = session.get(BackfillJob, job_id)
            assert event["event"] == "backfill_cooldown"
            assert job is not None
            assert job.status == "COOLDOWN"
            assert job.cooldown_until_ms == 7_000
            assert job.next_retry_at_ms == 7_000
    finally:
        engine.dispose()


def test_terminal_failure_when_attempt_budget_exhausted(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'backfill.db'}"
    engine, session_factory = _session_factory(db_url)
    try:
        with session_factory() as session:
            repo = BackfillRepoSql(session)
            jobs = repo.schedule_gap_jobs(
                symbol="BTCUSDC",
                timeframe="1m",
                gaps=[(300_000, 300_000)],
                priority=5,
                now_ms=0,
            )
            job_id = int(jobs[0].id)
            policy = BackfillRetryPolicy(max_attempts=1)
            event = repo.record_http_result(
                job_id=job_id,
                http_status=429,
                now_ms=1_000,
                headers={},
                policy=policy,
            )
            session.expire_all()
            job = session.get(BackfillJob, job_id)
            assert event["event"] == "backfill_failed_terminal"
            assert job is not None
            assert job.status == "FAILED_TERMINAL"
    finally:
        engine.dispose()
