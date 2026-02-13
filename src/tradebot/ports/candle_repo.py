from typing import Protocol, Sequence

from tradebot.domain.models.candle import Candle


class CandleRepo(Protocol):
    def upsert_candle(self, candle: Candle) -> None: ...

    def get_recent(self, symbol: str, tf: str, limit: int) -> Sequence[Candle]: ...
