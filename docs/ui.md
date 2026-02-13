# UI Pages

## Control page

- Route: `/`
- Purpose: daemon start/stop/status control

## Chart page

- Route: `/chart`
- Purpose: display initial candles history from local DB via chart API endpoints
- Visible timeframe selector with active state and keyboard navigation (`Left/Right/Up/Down/Home/End`)
- Visible active pair button opening an overlay list loaded from `GET /chart/symbols`

### Initial load behavior

- Tries `BTCUSDC` + `1m` first (`limit=500`)
- If empty, falls back to first available symbol/timeframe using `GET /chart/symbols` then `GET /chart/timeframes?symbol=...`
- Uses only backend API data (no direct Binance call from UI)
- Timeframe options come from `GET /chart/timeframes?symbol=...` with fixed fallback list: `1m`, `5m`, `15m`, `1h`, `4h`

### Timeframe switch behavior

- Changing timeframe reloads candles with `GET /chart/candles` while preserving current symbol
- In-flight candle request is aborted when a new timeframe is selected quickly
- If no data exists for selected timeframe, explicit empty state is shown

### Pair switch behavior

- Clicking the active pair opens an overlay listing available symbols from DB
- Keyboard navigation in the list: `Up/Down/Home/End`, `Enter` to select, `Escape` to close
- Selecting a pair closes the overlay and reloads candles while keeping the current timeframe

### Live refresh behavior

- Polling uses `GET /chart/candles` with `from_open_time_ms` based on the last rendered candle
- New candles are merged into current state without clearing the chart, keeping pair/timeframe selection
- `Derniere MAJ live` shows the timestamp of the latest successful polling cycle
- Temporary polling errors are shown as non-blocking live status and retried automatically
- When the tab is inactive, polling is slowed down (Page Visibility API)

### States

- `loading`: while fetching API data
- `empty`: no candles available for selection
- `error`: API/network failure with readable message

### Technical notes

- Responsive chart with `ResizeObserver`
- Canvas candlestick rendering (OHLC visible in header)
- Live refresh is polling-based and keeps the current chart state without full page reload
