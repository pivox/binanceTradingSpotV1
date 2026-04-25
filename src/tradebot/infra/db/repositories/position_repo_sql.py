from __future__ import annotations

import time
from decimal import Decimal

import structlog
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from tradebot.domain.models.position import Position, PositionStatus
from tradebot.infra.db.models import Position as PositionModel
from tradebot.infra.db.repositories._serializers import exit_plan_from_json, exit_plan_to_json

log = structlog.get_logger()


class PositionNotFoundError(Exception):
    pass


def _row_to_position(row: PositionModel) -> Position:
    from tradebot.domain.models.exit_plan import ExitPlan
    return Position(
        id=row.id,
        symbol=row.symbol,
        side=row.side,
        status=PositionStatus(row.status),
        entry_price=Decimal(str(row.entry_price)),
        quantity_total=Decimal(str(row.quantity_total)),
        stop_loss=Decimal(str(row.stop_loss)),
        atr_at_entry=Decimal(str(row.atr_at_entry)),
        signal_score=float(row.signal_score),
        setup_type=row.setup_type,
        shard_id=int(row.shard_id),
        opened_at_ms=int(row.opened_at_ms),
        exit_plan=exit_plan_from_json(row.exit_plan_json),
        high_since_entry=Decimal(str(row.high_since_entry)),
        closed_at_ms=row.closed_at_ms,
        last_checked_ms=row.last_checked_ms,
    )


class PositionRepoSql:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, position: Position) -> None:
        row = PositionModel(
            id=position.id,
            symbol=position.symbol,
            side=position.side,
            status=position.status.value,
            entry_price=str(position.entry_price),
            quantity_total=str(position.quantity_total),
            stop_loss=str(position.stop_loss),
            atr_at_entry=str(position.atr_at_entry),
            signal_score=position.signal_score,
            setup_type=position.setup_type,
            shard_id=position.shard_id,
            opened_at_ms=position.opened_at_ms,
            exit_plan_json=exit_plan_to_json(position.exit_plan),
            high_since_entry=str(position.high_since_entry),
            closed_at_ms=position.closed_at_ms,
            last_checked_ms=position.last_checked_ms,
        )
        self._session.add(row)
        self._session.flush()

    def get_by_id(self, position_id: str) -> Position | None:
        row = self._session.get(PositionModel, position_id)
        return _row_to_position(row) if row else None

    def get_open_by_symbol(self, symbol: str) -> Position | None:
        row = self._session.execute(
            select(PositionModel).where(
                PositionModel.symbol == symbol,
                PositionModel.status.in_(["ACTIVE", "OPEN_ENTRY_SENT", "CLOSING", "PENDING_ENTRY"]),
            ).limit(1)
        ).scalar_one_or_none()
        return _row_to_position(row) if row else None

    def list_open_by_shard(self, shard_id: int, due_before_ms: int) -> list[Position]:
        rows = self._session.execute(
            select(PositionModel).where(
                PositionModel.shard_id == shard_id,
                PositionModel.status.in_(["ACTIVE", "CLOSING"]),
                (PositionModel.last_checked_ms == None)  # noqa: E711
                | (PositionModel.last_checked_ms < due_before_ms),
            ).order_by(PositionModel.opened_at_ms.asc())
        ).scalars().all()
        return [_row_to_position(r) for r in rows]

    def update(self, position: Position) -> None:
        row = self._session.get(PositionModel, position.id)
        if row is None:
            raise PositionNotFoundError(position.id)
        row.status = position.status.value
        row.stop_loss = str(position.stop_loss)
        row.high_since_entry = str(position.high_since_entry)
        row.last_checked_ms = position.last_checked_ms
        row.closed_at_ms = position.closed_at_ms
        row.exit_plan_json = exit_plan_to_json(position.exit_plan)
        row.entry_price = str(position.entry_price)
        self._session.flush()

    def count_open(self) -> int:
        return self._session.execute(
            select(func.count()).where(
                PositionModel.status.in_(["ACTIVE", "OPEN_ENTRY_SENT", "CLOSING", "PENDING_ENTRY"])
            )
        ).scalar() or 0

    def count_open_by_symbol_prefix(self, prefix: str) -> int:
        return self._session.execute(
            select(func.count()).where(
                PositionModel.symbol.like(f"{prefix}%"),
                PositionModel.status.in_(["ACTIVE", "OPEN_ENTRY_SENT", "CLOSING", "PENDING_ENTRY"]),
            )
        ).scalar() or 0
