CREATE TABLE IF NOT EXISTS candles (
  symbol        TEXT   NOT NULL,
  timeframe     TEXT   NOT NULL,
  open_time_ms  BIGINT NOT NULL,
  close_time_ms BIGINT NOT NULL,
  open          NUMERIC NOT NULL,
  high          NUMERIC NOT NULL,
  low           NUMERIC NOT NULL,
  close         NUMERIC NOT NULL,
  volume        NUMERIC NOT NULL,
  is_partial    BOOLEAN NOT NULL DEFAULT FALSE,
  shard_id      INT NOT NULL,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(symbol, timeframe, open_time_ms)
);

CREATE TABLE IF NOT EXISTS candle_close_event (
  id           BIGSERIAL PRIMARY KEY,
  symbol       TEXT   NOT NULL,
  timeframe    TEXT   NOT NULL,
  open_time_ms BIGINT NOT NULL,
  shard_id     INT    NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(symbol, timeframe, open_time_ms)
);

CREATE TABLE IF NOT EXISTS candle_gap_request (
  id                BIGSERIAL PRIMARY KEY,
  symbol            TEXT NOT NULL,
  from_open_time_ms BIGINT NOT NULL,
  to_open_time_ms   BIGINT NOT NULL,
  detected_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS indicator_snapshots (
  id              BIGSERIAL PRIMARY KEY,
  symbol          TEXT NOT NULL,
  timeframe       TEXT NOT NULL,
  close_time_ms   BIGINT NOT NULL,
  computed_at_ms  BIGINT NOT NULL,
  schema_version  TEXT NOT NULL DEFAULT '1.0.0',
  payload_json    JSONB NOT NULL,
  etag            TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(symbol, timeframe, close_time_ms)
);

CREATE TABLE IF NOT EXISTS backfill_jobs (
  id                BIGSERIAL PRIMARY KEY,
  symbol            TEXT NOT NULL,
  timeframe         TEXT NOT NULL,
  from_open_time_ms BIGINT NOT NULL,
  to_open_time_ms   BIGINT NOT NULL,
  priority          INT NOT NULL DEFAULT 0,
  status            TEXT NOT NULL DEFAULT 'PENDING',
  attempts          INT NOT NULL DEFAULT 0,
  next_retry_at_ms  BIGINT NOT NULL DEFAULT 0,
  cooldown_until_ms BIGINT NOT NULL DEFAULT 0,
  last_http_status  INT NULL,
  last_error        TEXT NULL,
  last_weight_used  INT NULL,
  rate_mode         TEXT NOT NULL DEFAULT 'normal',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(symbol, timeframe, from_open_time_ms, to_open_time_ms)
);
