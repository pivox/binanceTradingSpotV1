from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from tradebot.domain.models.candle import Candle
from tradebot.infra.db.models import Candle as CandleModel


def _row_to_candle(row: CandleModel) -> Candle:
    return Candle(
        symbol=row.symbol,
        timeframe=row.timeframe,
        open_time_ms=row.open_time_ms,
        close_time_ms=row.close_time_ms,
        open=Decimal(str(row.open)),
        high=Decimal(str(row.high)),
        low=Decimal(str(row.low)),
        close=Decimal(str(row.close)),
        volume=Decimal(str(row.volume)),
        is_partial=bool(row.is_partial),
    )


class CandleRepoSql:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> list[Candle]:
        rows = (
            self._session.execute(
                select(CandleModel)
                .where(
                    CandleModel.symbol == symbol,
                    CandleModel.timeframe == timeframe,
                    CandleModel.is_partial == False,  # noqa: E712
                )
                .order_by(CandleModel.open_time_ms.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        # Inverser pour ordre ASC (plus vieille en premier)
        return [_row_to_candle(r) for r in reversed(rows)]

    def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
    ) -> list[Candle]:
        rows = (
            self._session.execute(
                select(CandleModel)
                .where(
                    CandleModel.symbol == symbol,
                    CandleModel.timeframe == timeframe,
                    CandleModel.open_time_ms >= start_ms,
                    CandleModel.open_time_ms <= end_ms,
                )
                .order_by(CandleModel.open_time_ms.asc())
            )
            .scalars()
            .all()
        )
        return [_row_to_candle(r) for r in rows]

    def fetch_symbols_with_timeframe(self, timeframe: str) -> list[str]:
        rows = (
            self._session.execute(
                select(CandleModel.symbol)
                .where(CandleModel.timeframe == timeframe)
                .distinct()
            )
            .scalars()
            .all()
        )
        return list(rows)

    def get_last_close_time(self, symbol: str, timeframe: str) -> int | None:
        result = self._session.execute(
            select(func.max(CandleModel.close_time_ms)).where(
                CandleModel.symbol == symbol,
                CandleModel.timeframe == timeframe,
                CandleModel.is_partial == False,  # noqa: E712
            )
        ).scalar()
        return result
