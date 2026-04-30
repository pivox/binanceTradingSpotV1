from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradebot.infra.db.models import Candle, IndicatorSnapshot

_TF_INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
}

_REQUIRED_TFS = ["4h", "1h", "15m", "5m", "1m"]
_CRITICAL_TFS = {"4h", "1h", "15m", "5m"}
_WARMUP_TF = "5m"
_WARMUP_CANDLES = 200
_GAP_FACTOR = 1.5
_MAX_GAPS = 10


@dataclass
class TfCoverage:
    timeframe: str
    candle_count: int
    first_ms: int | None
    last_ms: int | None
    coverage_pct: float
    gaps: list[dict]
    has_snapshots: bool
    status: str


@dataclass
class ReadinessResult:
    symbol: str
    from_ms: int
    to_ms: int
    profile: str
    timeframes: list[TfCoverage]
    warmup_ok: bool
    status: str
    reasons: list[str]


class ReadinessService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def check(
        self, symbol: str, from_ms: int, to_ms: int, profile: str = "regular"
    ) -> ReadinessResult:
        coverages: list[TfCoverage] = []
        for tf in _REQUIRED_TFS:
            coverages.append(self._check_tf(symbol, tf, from_ms, to_ms))

        warmup_ok = self._check_warmup(symbol, from_ms)

        reasons: list[str] = []
        global_status = "ready"

        for cov in coverages:
            if cov.timeframe in _CRITICAL_TFS and cov.status == "blocked":
                global_status = "blocked"
                reasons.append(
                    f"{cov.timeframe}: coverage too low ({cov.coverage_pct:.1f}%)"
                )
            elif cov.status == "warning" and global_status == "ready":
                global_status = "warning"
                reasons.append(
                    f"{cov.timeframe}: partial coverage ({cov.coverage_pct:.1f}%)"
                )

        if not warmup_ok:
            if global_status == "ready":
                global_status = "warning"
            reasons.append(
                f"Warmup insufficient: fewer than {_WARMUP_CANDLES} candles before window on {_WARMUP_TF}"
            )

        return ReadinessResult(
            symbol=symbol,
            from_ms=from_ms,
            to_ms=to_ms,
            profile=profile,
            timeframes=coverages,
            warmup_ok=warmup_ok,
            status=global_status,
            reasons=reasons,
        )

    def _check_tf(self, symbol: str, tf: str, from_ms: int, to_ms: int) -> TfCoverage:
        rows = (
            self._session.execute(
                select(Candle.open_time_ms)
                .where(
                    Candle.symbol == symbol,
                    Candle.timeframe == tf,
                    Candle.open_time_ms >= from_ms,
                    Candle.open_time_ms <= to_ms,
                    Candle.is_partial == False,  # noqa: E712
                )
                .order_by(Candle.open_time_ms)
            )
            .scalars()
            .all()
        )

        candle_count = len(rows)
        first_ms: int | None = rows[0] if rows else None
        last_ms: int | None = rows[-1] if rows else None

        interval_ms = _TF_INTERVAL_MS.get(tf, 60_000)
        duration_ms = to_ms - from_ms
        expected_count = max(1, duration_ms // interval_ms)
        coverage_pct = (
            (candle_count / expected_count) * 100.0 if expected_count > 0 else 0.0
        )

        gaps: list[dict] = []
        threshold = _GAP_FACTOR * interval_ms
        for i in range(1, len(rows)):
            diff = rows[i] - rows[i - 1]
            if diff > threshold:
                gaps.append({"from_ms": rows[i - 1], "to_ms": rows[i], "gap_ms": diff})
                if len(gaps) >= _MAX_GAPS:
                    break

        has_snapshots = (
            self._session.execute(
                select(IndicatorSnapshot.id)
                .where(
                    IndicatorSnapshot.symbol == symbol,
                    IndicatorSnapshot.timeframe == tf,
                    IndicatorSnapshot.close_time_ms >= from_ms,
                    IndicatorSnapshot.close_time_ms <= to_ms,
                )
                .limit(1)
            ).scalar()
            is not None
        )

        if coverage_pct >= 95.0:
            status = "ok"
        elif coverage_pct >= 70.0:
            status = "warning"
        else:
            status = "blocked"

        return TfCoverage(
            timeframe=tf,
            candle_count=candle_count,
            first_ms=first_ms,
            last_ms=last_ms,
            coverage_pct=coverage_pct,
            gaps=gaps,
            has_snapshots=has_snapshots,
            status=status,
        )

    def _check_warmup(self, symbol: str, from_ms: int) -> bool:
        count = (
            self._session.execute(
                select(Candle.open_time_ms)
                .where(
                    Candle.symbol == symbol,
                    Candle.timeframe == _WARMUP_TF,
                    Candle.open_time_ms < from_ms,
                    Candle.is_partial == False,  # noqa: E712
                )
                .order_by(Candle.open_time_ms.desc())
                .limit(_WARMUP_CANDLES)
            )
            .scalars()
            .all()
        )
        return len(count) >= _WARMUP_CANDLES
