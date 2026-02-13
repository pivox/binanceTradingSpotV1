from typing import Protocol, Sequence

from tradebot.domain.models.position import Position


class PositionRepo(Protocol):
    def list_due_positions(
        self, shard_id: int, now_ms: int, limit: int
    ) -> Sequence[Position]: ...

    def update_position(self, position: Position) -> None: ...
