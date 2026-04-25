from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tradebot.domain.models.mtf_state import MtfState
from tradebot.infra.db.models import MtfState as MtfStateModel
from tradebot.infra.db.repositories._serializers import (
    scores_by_tf_from_json,
    scores_by_tf_to_json,
)

log = structlog.get_logger()


def _row_to_state(row: MtfStateModel) -> MtfState:
    return MtfState(
        symbol=row.symbol,
        regime=row.regime,
        cascade_passed=bool(row.cascade_passed),
        score=float(row.score),
        quality=row.quality,
        active_setup=row.active_setup,
        scores_by_tf=scores_by_tf_from_json(row.scores_by_tf_json),
        rejection_reason=row.rejection_reason,
        evaluated_at_ms=int(row.evaluated_at_ms),
        signal_open_time_ms=row.signal_open_time_ms,
    )


class MtfStateRepoSql:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, symbol: str) -> MtfState | None:
        row = self._session.get(MtfStateModel, symbol)
        return _row_to_state(row) if row else None

    def upsert(self, state: MtfState) -> None:
        stmt = (
            insert(MtfStateModel)
            .values(
                symbol=state.symbol,
                regime=state.regime,
                cascade_passed=state.cascade_passed,
                score=state.score,
                quality=state.quality,
                active_setup=state.active_setup,
                scores_by_tf_json=scores_by_tf_to_json(state.scores_by_tf),
                rejection_reason=state.rejection_reason,
                evaluated_at_ms=state.evaluated_at_ms,
                signal_open_time_ms=state.signal_open_time_ms,
            )
            .on_conflict_do_update(
                index_elements=["symbol"],
                set_={
                    "regime": state.regime,
                    "cascade_passed": state.cascade_passed,
                    "score": state.score,
                    "quality": state.quality,
                    "active_setup": state.active_setup,
                    "scores_by_tf_json": scores_by_tf_to_json(state.scores_by_tf),
                    "rejection_reason": state.rejection_reason,
                    "evaluated_at_ms": state.evaluated_at_ms,
                    "signal_open_time_ms": state.signal_open_time_ms,
                },
            )
        )
        self._session.execute(stmt)
        self._session.flush()

    def list_all(self) -> list[MtfState]:
        rows = self._session.execute(select(MtfStateModel)).scalars().all()
        return [_row_to_state(r) for r in rows]

    def delete(self, symbol: str) -> None:
        row = self._session.get(MtfStateModel, symbol)
        if row:
            self._session.delete(row)
            self._session.flush()
