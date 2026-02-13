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
