from typing import Protocol, Sequence


class EventRepo(Protocol):
    def insert_candle_close_event(
        self, symbol: str, tf: str, open_time_ms: int, shard_id: int
    ) -> None: ...

    def fetch_candle_close_events(
        self, shard_id: int, last_event_id: int, limit: int
    ) -> Sequence[dict]: ...
