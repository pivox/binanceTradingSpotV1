from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import zlib

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from tradebot.infra.db.models import BackfillJob, Candle
from tradebot.observability.metrics import BACKFILL_EVENTS, BACKFILL_WEIGHT_USED


def timeframe_to_ms(timeframe: str) -> int:
    unit = timeframe[-1]
    amount = int(timeframe[:-1])
    multipliers = {
        "m": 60_000,
        "h": 3_600_000,
        "d": 86_400_000,
        "w": 604_800_000,
    }
    if amount <= 0 or unit not in multipliers:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    return amount * multipliers[unit]


@dataclass(frozen=True)
class BackfillRetryPolicy:
    max_attempts: int = 5
    base_backoff_ms: int = 500
    max_backoff_ms: int = 30_000
    max_retry_window_ms: int = 300_000
    cooldown_ms: int = 300_000
    weight_limit_1m: int = 1200
    slow_mode_threshold_ratio: float = 0.85


class BackfillRepoSql:
    def __init__(self, session: Session):
        self._session = session

    def detect_gaps(
        self,
        *,
        symbol: str,
        timeframe: str,
        from_open_time_ms: int | None = None,
        to_open_time_ms: int | None = None,
    ) -> list[tuple[int, int]]:
        step_ms = timeframe_to_ms(timeframe)
        stmt: Select[tuple[int]] = select(Candle.open_time_ms).where(
            Candle.symbol == symbol,
            Candle.timeframe == timeframe,
        )
        if from_open_time_ms is not None:
            stmt = stmt.where(Candle.open_time_ms >= from_open_time_ms)
        if to_open_time_ms is not None:
            stmt = stmt.where(Candle.open_time_ms <= to_open_time_ms)
        stmt = stmt.order_by(Candle.open_time_ms.asc())

        open_times = list(self._session.scalars(stmt))
        if not open_times:
            if (
                from_open_time_ms is not None
                and to_open_time_ms is not None
                and from_open_time_ms <= to_open_time_ms
            ):
                BACKFILL_EVENTS.labels(event="gap_detected", rate_mode="normal").inc()
                return [(from_open_time_ms, to_open_time_ms)]
            return []

        gaps: list[tuple[int, int]] = []
        if from_open_time_ms is not None and from_open_time_ms < open_times[0]:
            gap_end = open_times[0] - step_ms
            if from_open_time_ms <= gap_end:
                gaps.append((from_open_time_ms, gap_end))

        previous = open_times[0]
        for current in open_times[1:]:
            expected = previous + step_ms
            if current > expected:
                gaps.append((expected, current - step_ms))
            previous = current

        if to_open_time_ms is not None and previous < to_open_time_ms:
            tail_start = previous + step_ms
            if tail_start <= to_open_time_ms:
                gaps.append((tail_start, to_open_time_ms))
        if gaps:
            BACKFILL_EVENTS.labels(event="gap_detected", rate_mode="normal").inc(
                len(gaps)
            )
        return gaps

    def schedule_gap_jobs(
        self,
        *,
        symbol: str,
        timeframe: str,
        gaps: list[tuple[int, int]],
        priority: int,
        now_ms: int,
    ) -> list[BackfillJob]:
        created_jobs: list[BackfillJob] = []
        for from_ms, to_ms in gaps:
            existing = self._session.scalar(
                select(BackfillJob).where(
                    BackfillJob.symbol == symbol,
                    BackfillJob.timeframe == timeframe,
                    BackfillJob.from_open_time_ms == from_ms,
                    BackfillJob.to_open_time_ms == to_ms,
                )
            )
            if existing is not None:
                continue

            job = BackfillJob(
                symbol=symbol,
                timeframe=timeframe,
                from_open_time_ms=from_ms,
                to_open_time_ms=to_ms,
                priority=priority,
                status="PENDING",
                attempts=0,
                next_retry_at_ms=now_ms,
                cooldown_until_ms=0,
            )
            self._session.add(job)
            created_jobs.append(job)

        self._session.commit()
        return created_jobs

    def list_ready_jobs(self, *, now_ms: int, limit: int) -> list[BackfillJob]:
        stmt = (
            select(BackfillJob)
            .where(
                BackfillJob.status.in_(("PENDING", "RETRY_WAIT", "COOLDOWN")),
                BackfillJob.next_retry_at_ms <= now_ms,
                or_(
                    BackfillJob.cooldown_until_ms == 0,
                    BackfillJob.cooldown_until_ms <= now_ms,
                ),
            )
            .order_by(
                BackfillJob.priority.desc(),
                BackfillJob.next_retry_at_ms.asc(),
                BackfillJob.id.asc(),
            )
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def mark_in_progress(self, *, job_id: int) -> None:
        job = self._session.get(BackfillJob, job_id)
        if job is None:
            raise ValueError(f"unknown backfill job: {job_id}")
        job.status = "IN_PROGRESS"
        self._session.commit()

    def record_http_result(
        self,
        *,
        job_id: int,
        http_status: int,
        now_ms: int,
        policy: BackfillRetryPolicy,
        headers: dict[str, str] | None = None,
        error_message: str | None = None,
    ) -> dict[str, str | int | None]:
        job = self._session.get(BackfillJob, job_id)
        if job is None:
            raise ValueError(f"unknown backfill job: {job_id}")

        weight_used = _extract_weight(headers or {})
        rate_mode = _rate_mode(weight_used, policy)
        if weight_used is not None:
            BACKFILL_WEIGHT_USED.set(weight_used)
        job.last_http_status = http_status
        job.last_weight_used = weight_used
        job.rate_mode = rate_mode
        job.last_error = error_message

        if 200 <= http_status < 300:
            job.status = "DONE"
            job.next_retry_at_ms = now_ms
            job.cooldown_until_ms = 0
            self._session.commit()
            BACKFILL_EVENTS.labels(event="backfill_success", rate_mode=rate_mode).inc()
            return {
                "event": "backfill_success",
                "rate_mode": rate_mode,
                "weight": weight_used,
            }

        job.attempts += 1
        created_at_ms = _datetime_to_epoch_ms(job.created_at)
        elapsed_ms = max(0, now_ms - created_at_ms)
        terminal = (
            job.attempts >= policy.max_attempts
            or elapsed_ms >= policy.max_retry_window_ms
        )

        if http_status == 418 and not terminal:
            job.status = "COOLDOWN"
            job.cooldown_until_ms = now_ms + policy.cooldown_ms
            job.next_retry_at_ms = job.cooldown_until_ms
            self._session.commit()
            BACKFILL_EVENTS.labels(event="backfill_cooldown", rate_mode=rate_mode).inc()
            return {
                "event": "backfill_cooldown",
                "rate_mode": rate_mode,
                "weight": weight_used,
            }

        if terminal:
            job.status = "FAILED_TERMINAL"
            job.next_retry_at_ms = now_ms
            self._session.commit()
            BACKFILL_EVENTS.labels(
                event="backfill_failed_terminal", rate_mode=rate_mode
            ).inc()
            return {
                "event": "backfill_failed_terminal",
                "rate_mode": rate_mode,
                "weight": weight_used,
            }

        backoff_ms = _compute_backoff_ms(
            attempt=job.attempts,
            base_backoff_ms=policy.base_backoff_ms,
            max_backoff_ms=policy.max_backoff_ms,
            jitter_seed=f"{job.symbol}:{job.timeframe}:{job.id}:{job.attempts}",
        )
        job.status = "RETRY_WAIT"
        job.next_retry_at_ms = now_ms + backoff_ms
        job.cooldown_until_ms = 0
        self._session.commit()
        BACKFILL_EVENTS.labels(
            event="backfill_retry_scheduled", rate_mode=rate_mode
        ).inc()
        return {
            "event": "backfill_retry_scheduled",
            "rate_mode": rate_mode,
            "weight": weight_used,
        }


def _extract_weight(headers: dict[str, str]) -> int | None:
    weight_values: list[int] = []
    for key, value in headers.items():
        key_l = key.lower()
        if not key_l.startswith("x-mbx-used-weight"):
            continue
        try:
            weight_values.append(int(value.strip()))
        except ValueError:
            continue
    if not weight_values:
        return None
    return max(weight_values)


def _rate_mode(weight_used: int | None, policy: BackfillRetryPolicy) -> str:
    if weight_used is None:
        return "normal"
    threshold = int(policy.weight_limit_1m * policy.slow_mode_threshold_ratio)
    return "slow" if weight_used >= threshold else "normal"


def _compute_backoff_ms(
    *,
    attempt: int,
    base_backoff_ms: int,
    max_backoff_ms: int,
    jitter_seed: str,
) -> int:
    exp_backoff = base_backoff_ms * (2 ** max(0, attempt - 1))
    capped = min(exp_backoff, max_backoff_ms)
    jitter = 0.8 + ((zlib.crc32(jitter_seed.encode("utf-8")) % 41) / 100.0)
    return int(capped * jitter)


def _datetime_to_epoch_ms(value: datetime | None) -> int:
    if value is None:
        return 0
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    return int(aware.timestamp() * 1000)
