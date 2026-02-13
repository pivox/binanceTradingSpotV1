# Chart API

These endpoints expose read-only candle data from the local `candles` table.
All responses follow:

- Success: `{"ok": true, "data": ...}`
- Error: `{"ok": false, "error": {"code": "...", "message": "..."}}`

## Endpoints

### `GET /chart/symbols`

Returns sorted distinct symbols available in DB.

Example response:

```json
{
  "ok": true,
  "data": ["BTCUSDC", "ETHUSDC"]
}
```

### `GET /chart/timeframes`

Query params:

- `symbol` (optional): filter by symbol

Returns sorted distinct timeframes.

Examples:

- `/chart/timeframes`
- `/chart/timeframes?symbol=BTCUSDC`

### `GET /chart/candles`

Query params:

- `symbol` (required): `^[A-Z0-9]{2,20}$`
- `timeframe` (required): `^[1-9][0-9]*[mhdwM]$`
- `limit` (optional): default `500`, max `CHART_MAX_LIMIT` (default `1000`)
- `from_open_time_ms` (optional): strict `>` filter for incremental refresh

Notes:

- Without `from_open_time_ms`, returns the latest `limit` candles sorted by
  `open_time_ms` ascending.
- With `from_open_time_ms`, returns candles where `open_time_ms` is strictly
  greater than the provided value, also sorted ascending.

Example:

`/chart/candles?symbol=BTCUSDC&timeframe=1m&limit=500&from_open_time_ms=1739400000000`

Returned candle fields:

- `open`
- `high`
- `low`
- `close`
- `open_time_ms`
- `close_time_ms`
- `volume`
- `is_partial`
