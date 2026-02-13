def make_intent_key(prefix: str, symbol: str, open_time_ms: int) -> str:
    return f"{prefix}:{symbol}:{open_time_ms}"
