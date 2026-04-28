from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Select, distinct, select
from sqlalchemy.orm import Session

from tradebot.infra.db.models import Candle


class ChartRepository:
    def __init__(self, session: Session):
        self._session = session

    def list_symbols(self) -> list[str]:
        stmt = select(distinct(Candle.symbol)).order_by(Candle.symbol.asc())
        return list(self._session.scalars(stmt))

    def list_timeframes(self, symbol: str | None = None) -> list[str]:
        stmt: Select[Any] = select(distinct(Candle.timeframe))
        if symbol:
            stmt = stmt.where(Candle.symbol == symbol)
        stmt = stmt.order_by(Candle.timeframe.asc())
        return list(self._session.scalars(stmt))

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        from_open_time_ms: int | None = None,
        before_open_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        if from_open_time_ms is not None:
            stmt = (
                select(Candle)
                .where(
                    Candle.symbol == symbol,
                    Candle.timeframe == timeframe,
                    Candle.open_time_ms > from_open_time_ms,
                )
                .order_by(Candle.open_time_ms.asc())
                .limit(limit)
            )
            rows = list(self._session.scalars(stmt))
        elif before_open_time_ms is not None:
            # Historical scroll: fetch candles older than the current view.
            stmt = (
                select(Candle)
                .where(
                    Candle.symbol == symbol,
                    Candle.timeframe == timeframe,
                    Candle.open_time_ms < before_open_time_ms,
                )
                .order_by(Candle.open_time_ms.desc())
                .limit(limit)
            )
            rows = list(self._session.scalars(stmt))
            rows.reverse()
        else:
            # Return the latest window, but always sorted ascending for chart rendering.
            stmt = (
                select(Candle)
                .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
                .order_by(Candle.open_time_ms.desc())
                .limit(limit)
            )
            rows = list(self._session.scalars(stmt))
            rows.reverse()

        return [self._to_payload(row) for row in rows]

    def _to_payload(self, candle: Candle) -> dict[str, Any]:
        return {
            "open": self._as_float(candle.open),
            "high": self._as_float(candle.high),
            "low": self._as_float(candle.low),
            "close": self._as_float(candle.close),
            "open_time_ms": candle.open_time_ms,
            "close_time_ms": candle.close_time_ms,
            "volume": self._as_float(candle.volume),
            "is_partial": bool(candle.is_partial),
        }

    @staticmethod
    def _as_float(value: Decimal | float | int) -> float:
        return float(value)
