from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradebot.domain.models.mtf_signal import MTFSignal
from tradebot.infra.db.models import MtfSignalRecord


def _to_record(signal: MTFSignal) -> MtfSignalRecord:
    return MtfSignalRecord(
        symbol=signal.symbol,
        profile=signal.profile,
        trend_4h=signal.trend_4h,
        trend_1h=signal.trend_1h,
        structure_15m=signal.structure_15m,
        trigger_5m=signal.trigger_5m,
        score=signal.score,
        valid=signal.valid,
        blocking_filter=signal.blocking_filter,
        context_json=signal.context_json,
        evaluated_at_ms=signal.evaluated_at_ms,
    )


class MtfSignalRepoSql:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, signal: MTFSignal) -> None:
        """Persiste chaque signal évalué (y compris valid=False) pour audit."""
        self._session.add(_to_record(signal))
        self._session.flush()

    def list_valid(self, symbol: str, limit: int = 100) -> list[MTFSignal]:
        rows = (
            self._session.execute(
                select(MtfSignalRecord)
                .where(MtfSignalRecord.symbol == symbol)
                .where(MtfSignalRecord.valid.is_(True))
                .order_by(MtfSignalRecord.evaluated_at_ms.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [_from_record(r) for r in rows]

    def list_all(self, symbol: str, limit: int = 500) -> list[MTFSignal]:
        rows = (
            self._session.execute(
                select(MtfSignalRecord)
                .where(MtfSignalRecord.symbol == symbol)
                .order_by(MtfSignalRecord.evaluated_at_ms.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [_from_record(r) for r in rows]


def _from_record(row: MtfSignalRecord) -> MTFSignal:
    return MTFSignal(
        symbol=row.symbol,
        profile=row.profile,
        trend_4h=bool(row.trend_4h),
        trend_1h=bool(row.trend_1h),
        structure_15m=bool(row.structure_15m),
        trigger_5m=bool(row.trigger_5m),
        score=int(row.score),
        valid=bool(row.valid),
        blocking_filter=row.blocking_filter,
        context_json=dict(row.context_json),
        evaluated_at_ms=int(row.evaluated_at_ms),
    )
