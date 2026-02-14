# Backfill gaps and rate-limit policy

Implementation scope for `T-0023`:

- Gap detection on `candles` timeline by `(symbol,timeframe)`
- Backfill jobs persisted in `backfill_jobs`
- Prioritized scheduler read (`priority desc`, then retry timestamp)
- Binance weight interpretation from `X-MBX-USED-WEIGHT-*` headers
- Policies:
  - `429`: bounded retry with exponential backoff + deterministic jitter
  - `418`: hard cooldown with explicit resume timestamp
  - terminal stop when retry budget is exhausted

## Job lifecycle

- `PENDING` -> `IN_PROGRESS`
- `IN_PROGRESS` -> `DONE` (2xx)
- `IN_PROGRESS` -> `RETRY_WAIT` (retryable error)
- `IN_PROGRESS` -> `COOLDOWN` (`418`)
- `IN_PROGRESS` -> `FAILED_TERMINAL` (max attempts/window reached)

## Config knobs (`Settings`)

- `backfill_max_attempts`
- `backfill_base_backoff_ms`
- `backfill_max_backoff_ms`
- `backfill_max_retry_window_ms`
- `backfill_cooldown_ms`
- `backfill_weight_limit_1m`
- `backfill_slow_mode_threshold_ratio`
