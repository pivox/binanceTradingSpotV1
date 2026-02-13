from typing import List

from tradebot.domain.models.order_intent import OrderIntent


def compute_exit_intents() -> List[OrderIntent]:
    raise NotImplementedError
