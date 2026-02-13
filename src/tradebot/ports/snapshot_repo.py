from typing import Protocol, Sequence


class SnapshotRepo(Protocol):
    def upsert_snapshot(
        self, symbol: str, tf: str, open_time_ms: int, payload: dict
    ) -> None: ...

    def get_latest_snapshots(self, symbol: str, tfs: Sequence[str]) -> dict: ...
