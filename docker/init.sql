-- ─────────────────────────────────────────────────────────────────────────────
-- Candles & market data
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS candles (
  symbol        TEXT          NOT NULL,
  timeframe     TEXT          NOT NULL,
  open_time_ms  BIGINT        NOT NULL,
  close_time_ms BIGINT        NOT NULL,
  open          NUMERIC       NOT NULL,
  high          NUMERIC       NOT NULL,
  low           NUMERIC       NOT NULL,
  close         NUMERIC       NOT NULL,
  volume        NUMERIC       NOT NULL,
  is_partial    BOOLEAN       NOT NULL DEFAULT FALSE,
  shard_id      INT           NOT NULL,
  updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
  PRIMARY KEY(symbol, timeframe, open_time_ms)
);

CREATE TABLE IF NOT EXISTS candle_close_event (
  id           BIGSERIAL   PRIMARY KEY,
  symbol       TEXT        NOT NULL,
  timeframe    TEXT        NOT NULL,
  open_time_ms BIGINT      NOT NULL,
  shard_id     INT         NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(symbol, timeframe, open_time_ms)
);

CREATE TABLE IF NOT EXISTS candle_close_event_processed (
  id              BIGINT PRIMARY KEY,  -- FK to candle_close_event.id
  processed_at_ms BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS candle_gap_request (
  id                BIGSERIAL   PRIMARY KEY,
  symbol            TEXT        NOT NULL,
  from_open_time_ms BIGINT      NOT NULL,
  to_open_time_ms   BIGINT      NOT NULL,
  detected_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Indicators & backfill
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS indicator_snapshots (
  id             BIGSERIAL   PRIMARY KEY,
  symbol         TEXT        NOT NULL,
  timeframe      TEXT        NOT NULL,
  close_time_ms  BIGINT      NOT NULL,
  computed_at_ms BIGINT      NOT NULL,
  schema_version TEXT        NOT NULL DEFAULT '1.0.0',
  payload_json   JSONB       NOT NULL,
  etag           TEXT        NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_indicator_snapshots_symbol_tf_close_time UNIQUE(symbol, timeframe, close_time_ms)
);

CREATE TABLE IF NOT EXISTS backfill_jobs (
  id                BIGSERIAL   PRIMARY KEY,
  symbol            TEXT        NOT NULL,
  timeframe         TEXT        NOT NULL,
  from_open_time_ms BIGINT      NOT NULL,
  to_open_time_ms   BIGINT      NOT NULL,
  priority          INT         NOT NULL DEFAULT 0,
  status            TEXT        NOT NULL DEFAULT 'PENDING',
  attempts          INT         NOT NULL DEFAULT 0,
  next_retry_at_ms  BIGINT      NOT NULL DEFAULT 0,
  cooldown_until_ms BIGINT      NOT NULL DEFAULT 0,
  last_http_status  INT         NULL,
  last_error        TEXT        NULL,
  last_weight_used  INT         NULL,
  rate_mode         TEXT        NOT NULL DEFAULT 'normal',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(symbol, timeframe, from_open_time_ms, to_open_time_ms)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Exchange info cache
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS exchange_info_cache (
  symbol            TEXT    PRIMARY KEY,
  status            TEXT    NOT NULL DEFAULT 'UNKNOWN',
  base_asset        TEXT    NOT NULL DEFAULT '',
  quote_asset       TEXT    NOT NULL DEFAULT '',
  price_tick_size   NUMERIC NULL,
  price_min         NUMERIC NULL,
  price_max         NUMERIC NULL,
  qty_step_size     NUMERIC NULL,
  qty_min           NUMERIC NULL,
  qty_max           NUMERIC NULL,
  min_notional      NUMERIC NULL,
  max_notional      NUMERIC NULL,
  order_types_json  JSONB   NOT NULL DEFAULT '[]',
  permissions_json  JSONB   NOT NULL DEFAULT '[]',
  filters_json      JSONB   NOT NULL DEFAULT '[]',
  payload_json      JSONB   NOT NULL DEFAULT '{}',
  fetched_at_ms     BIGINT  NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Trading pipeline
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS positions (
  id               TEXT          PRIMARY KEY,  -- UUID
  symbol           TEXT          NOT NULL,
  side             TEXT          NOT NULL,     -- 'BUY'
  status           TEXT          NOT NULL,     -- PENDING_ENTRY | OPEN_ENTRY_SENT | ACTIVE | CLOSING | CLOSED
  entry_price      NUMERIC(20,8) NOT NULL,
  quantity_total   NUMERIC(20,8) NOT NULL,
  stop_loss        NUMERIC(20,8) NOT NULL,
  atr_at_entry     NUMERIC(20,8) NOT NULL,
  signal_score     FLOAT         NOT NULL,
  setup_type       TEXT          NOT NULL,     -- 'A'|'B'|'C'|'D'
  shard_id         SMALLINT      NOT NULL,
  opened_at_ms     BIGINT        NOT NULL,
  closed_at_ms     BIGINT        NULL,
  exit_plan_json   TEXT          NOT NULL,
  high_since_entry NUMERIC(20,8) NOT NULL,
  last_checked_ms  BIGINT        NULL,
  created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_positions_shard_status_checked
  ON positions(shard_id, status, last_checked_ms);
CREATE INDEX IF NOT EXISTS ix_positions_symbol_status
  ON positions(symbol, status);

CREATE TABLE IF NOT EXISTS order_intents (
  id               TEXT          PRIMARY KEY,  -- UUID
  intent_key       TEXT          NOT NULL UNIQUE,
  position_id      TEXT          NULL,
  symbol           TEXT          NOT NULL,
  side             TEXT          NOT NULL,     -- 'BUY'|'SELL'
  order_type       TEXT          NOT NULL,     -- 'LIMIT'|'MARKET'|'STOP_MARKET'
  quantity         NUMERIC(20,8) NOT NULL,
  price            NUMERIC(20,8) NULL,
  stop_price       NUMERIC(20,8) NULL,
  lot_id           TEXT          NULL,         -- 'A'|'B'|'C'
  status           TEXT          NOT NULL DEFAULT 'PENDING',
  binance_order_id BIGINT        NULL,
  filled_qty       NUMERIC(20,8) NULL,
  avg_price        NUMERIC(20,8) NULL,
  error_msg        TEXT          NULL,
  created_at_ms    BIGINT        NOT NULL,
  updated_at_ms    BIGINT        NOT NULL,
  created_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_order_intents_symbol_status
  ON order_intents(symbol, status);
CREATE INDEX IF NOT EXISTS ix_order_intents_position
  ON order_intents(position_id);

CREATE TABLE IF NOT EXISTS pnl_trades (
  id              BIGSERIAL     PRIMARY KEY,
  position_id     TEXT          NOT NULL UNIQUE,
  symbol          TEXT          NOT NULL,
  opened_at_ms    BIGINT        NOT NULL,
  closed_at_ms    BIGINT        NOT NULL,
  entry_price     NUMERIC(20,8) NOT NULL,
  exit_price_avg  NUMERIC(20,8) NOT NULL,
  quantity_total  NUMERIC(20,8) NOT NULL,
  realized_pnl    NUMERIC(20,8) NOT NULL,
  created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_pnl_trades_closed_at
  ON pnl_trades(closed_at_ms);

CREATE TABLE IF NOT EXISTS mtf_states (
  symbol              TEXT    PRIMARY KEY,
  regime              TEXT    NOT NULL,
  cascade_passed      BOOLEAN NOT NULL,
  score               FLOAT   NOT NULL,
  quality             TEXT    NOT NULL,
  active_setup        TEXT    NULL,
  scores_by_tf_json   TEXT    NOT NULL DEFAULT '{}',
  rejection_reason    TEXT    NULL,
  evaluated_at_ms     BIGINT  NOT NULL,
  signal_open_time_ms BIGINT  NULL,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
