from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradebot.infra.db.models import IndicatorSnapshot


class SnapshotRepoSql:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        from_ms: int,
        to_ms: int,
    ) -> list[tuple[int, dict]]:
        """Returns (close_time_ms, payload_json) pairs sorted ASC by close_time_ms."""
        rows = self._session.execute(
            select(IndicatorSnapshot.close_time_ms, IndicatorSnapshot.payload_json)
            .where(
                IndicatorSnapshot.symbol == symbol,
                IndicatorSnapshot.timeframe == timeframe,
                IndicatorSnapshot.close_time_ms >= from_ms,
                IndicatorSnapshot.close_time_ms <= to_ms,
            )
            .order_by(IndicatorSnapshot.close_time_ms.asc())
        ).all()
        return [(row.close_time_ms, row.payload_json) for row in rows]
