from dataclasses import dataclass
from enum import Enum


class SignalReason(str, Enum):
    MTF_OK = "mtf_ok"
    MTF_FAIL = "mtf_fail"


@dataclass(frozen=True)
class Signal:
    symbol: str
    tf: str
    side: str
    reason: SignalReason
