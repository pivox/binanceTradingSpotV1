from __future__ import annotations

from typing import Sequence

DAY_MS = 86_400_000


def vwap(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    close_times_ms: Sequence[int],
) -> float:
    if not (len(highs) == len(lows) == len(closes) == len(volumes) == len(close_times_ms)):
        raise ValueError("all sequences must have the same length")
    if not highs:
        raise ValueError("cannot compute vwap with empty data")

    latest_session = close_times_ms[-1] // DAY_MS
    cumulative_tp_vol = 0.0
    cumulative_vol = 0.0
    for hi, lo, cl, vol, ts in zip(highs, lows, closes, volumes, close_times_ms):
        if ts // DAY_MS == latest_session:
            cumulative_tp_vol += ((hi + lo + cl) / 3.0) * vol
            cumulative_vol += vol

    if cumulative_vol <= 0:
        raise ValueError("cannot compute vwap with zero volume")
    return cumulative_tp_vol / cumulative_vol
