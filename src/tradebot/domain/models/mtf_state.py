from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class MtfState:
    symbol: str
    shard_id: int
    ctx_4h_ok: bool = False
    ctx_1h_ok: bool = False
    ctx_15m_ok: bool = False
    ctx_5m_ok: bool = False
    last_eval_1m_open_time: Optional[int] = None
    retry_counters: Dict[str, int] | None = None
    next_allowed_eval_at: Optional[int] = None
