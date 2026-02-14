from prometheus_client import Counter, Gauge, Histogram


TRADEBOT_EVENTS = Counter("tradebot_events_total", "Total events")
BACKFILL_EVENTS = Counter(
    "tradebot_backfill_events_total",
    "Backfill event count by type",
    ("event", "rate_mode"),
)
BACKFILL_WEIGHT_USED = Gauge(
    "tradebot_backfill_weight_used",
    "Last observed Binance used weight header value",
)
INDICATOR_API_LATENCY_MS = Histogram(
    "tradebot_indicator_api_latency_ms",
    "Indicators API latency in milliseconds",
    ("endpoint", "result"),
    buckets=(50, 100, 200, 300, 500, 1000, 2000, 5000),
)
INDICATOR_CACHE_REQUESTS = Counter(
    "tradebot_indicator_cache_requests_total",
    "Conditional cache request outcomes for /indicators/latest",
    ("result",),
)
INDICATOR_SNAPSHOT_FRESHNESS_MS = Gauge(
    "tradebot_indicator_snapshot_freshness_ms",
    "Freshness of latest indicator snapshots in milliseconds",
    ("symbol", "timeframe"),
)
