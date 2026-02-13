from prometheus_client import Counter


TRADEBOT_EVENTS = Counter("tradebot_events_total", "Total events")
