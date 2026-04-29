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

    # (ts - 1) // DAY_MS: a candle closing exactly at midnight belongs to the
    # previous session (its open was 23:59:xx), not the new day.
    latest_session = (close_times_ms[-1] - 1) // DAY_MS
    cumulative_tp_vol = 0.0
    cumulative_vol = 0.0
    for i in range(len(close_times_ms) - 1, -1, -1):
        if (close_times_ms[i] - 1) // DAY_MS != latest_session:
            break
        cumulative_tp_vol += ((highs[i] + lows[i] + closes[i]) / 3.0) * volumes[i]
        cumulative_vol += volumes[i]

    if cumulative_vol <= 0:
        raise ValueError("cannot compute vwap with zero volume")
    return cumulative_tp_vol / cumulative_vol
