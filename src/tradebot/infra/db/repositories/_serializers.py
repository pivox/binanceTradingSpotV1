from __future__ import annotations

import json
from decimal import Decimal

from tradebot.domain.models.exit_plan import ExitPlan, Lot, LotRule


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Not serializable: {type(obj)}")


def exit_plan_to_json(plan: ExitPlan) -> str:
    data = {
        "r_distance": str(plan.r_distance),
        "lots": [
            {
                "id": lot.id,
                "pct": lot.pct,
                "rule": {
                    "type": lot.rule.type,
                    "r_multiple": lot.rule.r_multiple,
                    "atr_tf": lot.rule.atr_tf,
                    "atr_multiplier": lot.rule.atr_multiplier,
                },
                "quantity": str(lot.quantity),
                "is_filled": lot.is_filled,
                "fill_price": str(lot.fill_price) if lot.fill_price is not None else None,
                "fill_time_ms": lot.fill_time_ms,
                "current_trailing": str(lot.current_trailing) if lot.current_trailing is not None else None,
                "binance_order_id": lot.binance_order_id,
            }
            for lot in plan.lots
        ],
    }
    return json.dumps(data)


def exit_plan_from_json(raw: str) -> ExitPlan:
    data = json.loads(raw)
    lots = []
    for d in data["lots"]:
        rule = LotRule(
            type=d["rule"]["type"],
            r_multiple=d["rule"]["r_multiple"],
            atr_tf=d["rule"]["atr_tf"],
            atr_multiplier=d["rule"]["atr_multiplier"],
        )
        lot = Lot(
            id=d["id"],
            pct=d["pct"],
            rule=rule,
            quantity=Decimal(d["quantity"]),
            is_filled=d["is_filled"],
            fill_price=Decimal(d["fill_price"]) if d.get("fill_price") else None,
            fill_time_ms=d.get("fill_time_ms"),
            current_trailing=Decimal(d["current_trailing"]) if d.get("current_trailing") else None,
            binance_order_id=d.get("binance_order_id"),
        )
        lots.append(lot)
    lot_a, lot_b, lot_c = lots[0], lots[1], lots[2]
    return ExitPlan(
        lot_a=lot_a,
        lot_b=lot_b,
        lot_c=lot_c,
        r_distance=Decimal(data["r_distance"]),
    )


def scores_by_tf_to_json(scores: dict) -> str:
    return json.dumps(scores)


def scores_by_tf_from_json(raw: str) -> dict:
    return json.loads(raw)
