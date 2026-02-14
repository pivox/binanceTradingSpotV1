from __future__ import annotations

import base64
from hashlib import sha256
import json
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from tradebot.infra.db.models import IndicatorSnapshot


class InvalidCursorError(ValueError):
    pass


class IndicatorRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert_snapshot(
        self,
        *,
        symbol: str,
        timeframe: str,
        close_time_ms: int,
        computed_at_ms: int,
        schema_version: str,
        payload: dict[str, Any],
    ) -> IndicatorSnapshot:
        row = self._session.scalar(
            select(IndicatorSnapshot).where(
                IndicatorSnapshot.symbol == symbol,
                IndicatorSnapshot.timeframe == timeframe,
                IndicatorSnapshot.close_time_ms == close_time_ms,
            )
        )
        etag = self._make_etag(
            symbol=symbol,
            timeframe=timeframe,
            close_time_ms=close_time_ms,
            computed_at_ms=computed_at_ms,
            schema_version=schema_version,
        )

        if row is None:
            row = IndicatorSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                close_time_ms=close_time_ms,
                computed_at_ms=computed_at_ms,
                schema_version=schema_version,
                payload_json=payload,
                etag=etag,
            )
            self._session.add(row)
        else:
            row.computed_at_ms = computed_at_ms
            row.schema_version = schema_version
            row.payload_json = payload
            row.etag = etag

        self._session.commit()
        self._session.refresh(row)
        return row

    def get_latest_snapshot(
        self, *, symbol: str, timeframe: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        row = self._session.scalar(
            select(IndicatorSnapshot)
            .where(
                IndicatorSnapshot.symbol == symbol,
                IndicatorSnapshot.timeframe == timeframe,
            )
            .order_by(
                IndicatorSnapshot.close_time_ms.desc(),
                IndicatorSnapshot.id.desc(),
            )
            .limit(1)
        )
        if row is None:
            return None, None
        return self._to_api_payload(row), row.etag

    def get_history(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        cursor_close_time_ms, cursor_id = self._decode_cursor(cursor)

        stmt = select(IndicatorSnapshot).where(
            IndicatorSnapshot.symbol == symbol,
            IndicatorSnapshot.timeframe == timeframe,
        )
        if cursor_close_time_ms is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    IndicatorSnapshot.close_time_ms < cursor_close_time_ms,
                    and_(
                        IndicatorSnapshot.close_time_ms == cursor_close_time_ms,
                        IndicatorSnapshot.id < cursor_id,
                    ),
                )
            )

        rows = list(
            self._session.scalars(
                stmt.order_by(
                    IndicatorSnapshot.close_time_ms.desc(),
                    IndicatorSnapshot.id.desc(),
                ).limit(limit + 1)
            )
        )

        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = self._encode_cursor(last.close_time_ms, int(last.id))

        return [self._to_api_payload(row) for row in page_rows], next_cursor

    @staticmethod
    def _to_api_payload(row: IndicatorSnapshot) -> dict[str, Any]:
        payload = dict(row.payload_json or {})
        return {
            "schema_version": row.schema_version,
            "symbol": row.symbol,
            "timeframe": row.timeframe,
            "close_time": row.close_time_ms,
            "computed_at": row.computed_at_ms,
            **payload,
        }

    @staticmethod
    def _make_etag(
        *,
        symbol: str,
        timeframe: str,
        close_time_ms: int,
        computed_at_ms: int,
        schema_version: str,
    ) -> str:
        raw = (
            f"{symbol}:{timeframe}:{close_time_ms}:{computed_at_ms}:{schema_version}"
        ).encode("utf-8")
        return f'"{sha256(raw).hexdigest()}"'

    @staticmethod
    def _encode_cursor(close_time_ms: int, row_id: int) -> str:
        payload = {"close_time_ms": close_time_ms, "id": row_id}
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> tuple[int | None, int | None]:
        if cursor is None:
            return None, None
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
            payload = json.loads(decoded)
            close_time_ms = int(payload["close_time_ms"])
            row_id = int(payload["id"])
            if close_time_ms < 0 or row_id <= 0:
                raise ValueError("cursor values out of range")
            return close_time_ms, row_id
        except Exception as exc:
            raise InvalidCursorError("invalid cursor") from exc
