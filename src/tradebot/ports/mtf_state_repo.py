from typing import Protocol

from tradebot.domain.models.mtf_state import MtfState


class MtfStateRepo(Protocol):
    def get_state(self, symbol: str) -> MtfState | None: ...

    def upsert_state(self, state: MtfState) -> None: ...
