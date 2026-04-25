from __future__ import annotations

import time
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tradebot.domain.models.order_intent import OrderIntent, OrderIntentStatus, Side, OrderType
from tradebot.infra.db.models import OrderIntent as OrderIntentModel

log = structlog.get_logger()


def _row_to_intent(row: OrderIntentModel) -> OrderIntent:
    return OrderIntent(
        id=row.id,
        intent_key=row.intent_key,
        symbol=row.symbol,
        side=Side(row.side),
        order_type=OrderType(row.order_type),
        quantity=Decimal(str(row.quantity)),
        status=OrderIntentStatus(row.status),
        price=Decimal(str(row.price)) if row.price is not None else None,
        stop_price=Decimal(str(row.stop_price)) if row.stop_price is not None else None,
        lot_id=row.lot_id,
        position_id=row.position_id,
        binance_order_id=row.binance_order_id,
        filled_qty=Decimal(str(row.filled_qty)) if row.filled_qty is not None else None,
        avg_price=Decimal(str(row.avg_price)) if row.avg_price is not None else None,
        error_msg=row.error_msg,
        created_at_ms=row.created_at_ms,
        updated_at_ms=row.updated_at_ms,
    )


class OrderIntentRepoSql:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, intent: OrderIntent) -> None:
        now_ms = int(time.time() * 1000)
        stmt = (
            insert(OrderIntentModel)
            .values(
                id=intent.id,
                intent_key=intent.intent_key,
                position_id=intent.position_id,
                symbol=intent.symbol,
                side=intent.side.value,
                order_type=intent.order_type.value,
                quantity=str(intent.quantity),
                price=str(intent.price) if intent.price is not None else None,
                stop_price=str(intent.stop_price) if intent.stop_price is not None else None,
                lot_id=intent.lot_id,
                status=intent.status.value,
                binance_order_id=intent.binance_order_id,
                filled_qty=str(intent.filled_qty) if intent.filled_qty is not None else None,
                avg_price=str(intent.avg_price) if intent.avg_price is not None else None,
                error_msg=intent.error_msg,
                created_at_ms=intent.created_at_ms or now_ms,
                updated_at_ms=intent.updated_at_ms or now_ms,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        self._session.execute(stmt)
        self._session.flush()

    def get_by_id(self, intent_id: str) -> OrderIntent | None:
        row = self._session.get(OrderIntentModel, intent_id)
        return _row_to_intent(row) if row else None

    def get_by_intent_key(self, intent_key: str) -> OrderIntent | None:
        row = self._session.execute(
            select(OrderIntentModel).where(OrderIntentModel.intent_key == intent_key)
        ).scalar_one_or_none()
        return _row_to_intent(row) if row else None

    def update_status(
        self,
        intent_id: str,
        status: OrderIntentStatus,
        binance_order_id: Optional[int] = None,
        filled_qty: Optional[Decimal] = None,
        avg_price: Optional[Decimal] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        row = self._session.get(OrderIntentModel, intent_id)
        if row is None:
            log.warning("order_intent_not_found_for_update", intent_id=intent_id)
            return
        row.status = status.value
        row.updated_at_ms = int(time.time() * 1000)
        if binance_order_id is not None:
            row.binance_order_id = binance_order_id
        if filled_qty is not None:
            row.filled_qty = str(filled_qty)
        if avg_price is not None:
            row.avg_price = str(avg_price)
        if error_msg is not None:
            row.error_msg = error_msg
        self._session.flush()

    def list_pending_by_symbol(self, symbol: str) -> list[OrderIntent]:
        rows = self._session.execute(
            select(OrderIntentModel).where(
                OrderIntentModel.symbol == symbol,
                OrderIntentModel.status.in_(["PENDING", "SENT", "PARTIALLY_FILLED"]),
            )
        ).scalars().all()
        return [_row_to_intent(r) for r in rows]

    def list_active(self) -> list[OrderIntent]:
        rows = self._session.execute(
            select(OrderIntentModel).where(
                OrderIntentModel.status.in_(["PENDING", "SENT", "PARTIALLY_FILLED"])
            )
        ).scalars().all()
        return [_row_to_intent(r) for r in rows]

    def list_by_position(self, position_id: str) -> list[OrderIntent]:
        rows = self._session.execute(
            select(OrderIntentModel).where(OrderIntentModel.position_id == position_id)
        ).scalars().all()
        return [_row_to_intent(r) for r in rows]
