from __future__ import annotations

import time
from typing import Optional

import structlog

from tradebot.config.types import StrategyConfig
from tradebot.domain.models.cascade_result import CascadeResult, MarketRegime
from tradebot.domain.models.signal import SignalQuality, SetupType
from tradebot.services.mtf._conditions import (
    adx_trending_up,
    bollinger_squeeze,
    ema_aligned_up,
    macd_histogram_positive,
    macd_positive_or_crossing,
    price_above_ema,
    price_above_upper_bb,
    price_above_vwap,
    price_between_ema20_ema50,
    price_near_pivot,
    rsi_above,
    rsi_in_range,
    rsi_not_overbought,
    stochrsi_crossing_up,
    volume_above_average,
)
from tradebot.services.mtf.regime import detect_regime

log = structlog.get_logger()

_WEIGHTS = {"4h": 2.0, "1h": 1.5, "15m": 1.0, "5m": 0.8}
_TOTAL_WEIGHT = sum(_WEIGHTS.values())


def _score_4h(snap: dict) -> float:
    conditions = [
        ema_aligned_up(snap, "ema20", "ema50"),
        price_above_ema(snap, "ema50"),
        rsi_above(snap, 45),
        macd_positive_or_crossing(snap),
        adx_trending_up(snap) or (snap.get("adx", {}).get("value", 0) > 20),
    ]
    return sum(conditions) / len(conditions)


def _score_1h(snap: dict) -> float:
    conditions = [
        ema_aligned_up(snap, "ema20", "ema50"),
        price_above_vwap(snap),
        adx_trending_up(snap),
        rsi_in_range(snap, 50, 70),
        macd_histogram_positive(snap),
    ]
    return sum(conditions) / len(conditions)


def _select_setup(
    regime: MarketRegime,
    snap_15m: dict,
    snap_1h: dict,
) -> Optional[SetupType]:
    if regime == MarketRegime.TRENDING_UP:
        if price_between_ema20_ema50(snap_15m):
            return SetupType.A
        if bollinger_squeeze(snap_1h) and price_above_upper_bb(snap_15m):
            return SetupType.B
        if price_near_pivot(snap_15m):
            return SetupType.C
        return SetupType.A
    if regime == MarketRegime.RANGING:
        if price_near_pivot(snap_15m):
            return SetupType.C
        return SetupType.B
    if regime == MarketRegime.RECOVERY:
        return SetupType.D
    return None


def _score_15m(snap: dict, setup: SetupType) -> float:
    if setup == SetupType.A:
        conditions = [
            price_between_ema20_ema50(snap),
            rsi_in_range(snap, 40, 60),
            True,  # volume faible du pullback — simplifié, nécessite série historique
            ema_aligned_up(snap, "ema20", "ema50"),
            macd_histogram_positive(snap),
        ]
    elif setup == SetupType.B:
        conditions = [
            price_above_upper_bb(snap),
            volume_above_average(snap, 2.0),
            rsi_not_overbought(snap, 65),
            price_above_ema(snap, "ema20"),
            macd_positive_or_crossing(snap),
        ]
    elif setup == SetupType.C:
        conditions = [
            price_near_pivot(snap),
            rsi_in_range(snap, 35, 55),
            macd_positive_or_crossing(snap),
            ema_aligned_up(snap, "ema20", "ema50"),
            True,
        ]
    else:  # SetupType.D
        conditions = [
            ema_aligned_up(snap, "ema20", "ema50"),
            rsi_above(snap, 50),
            macd_positive_or_crossing(snap),
            adx_trending_up(snap),
            True,
        ]
    return sum(conditions) / len(conditions)


def _score_5m(snap: dict) -> float:
    conditions = [
        stochrsi_crossing_up(snap, max_k=0.30),
        macd_histogram_positive(snap) or macd_positive_or_crossing(snap),
        price_above_ema(snap, "ema9"),
        volume_above_average(snap, 1.0),
    ]
    return sum(conditions) / len(conditions)


def evaluate_cascade(
    symbol: str,
    snapshots: dict[str, dict],
    prev_snapshot_1h: Optional[dict] = None,
    config: Optional[StrategyConfig] = None,
) -> CascadeResult:
    now_ms = int(time.time() * 1000)

    def _reject(reason: str, scores: dict = {}) -> CascadeResult:
        return CascadeResult(
            symbol=symbol,
            regime=MarketRegime.RANGING,
            cascade_passed=False,
            score=0.0,
            quality=SignalQuality.REJECTED,
            active_setup=None,
            scores_by_tf=scores,
            rejection_reason=reason,
            evaluated_at_ms=now_ms,
        )

    # Vérifier présence de chaque timeframe requis
    for tf in ("4h", "1h", "15m", "5m"):
        if tf not in snapshots or snapshots[tf] is None:
            return _reject(f"missing_snapshot_{tf}")

    snap_4h = snapshots["4h"]
    snap_1h = snapshots["1h"]
    snap_15m = snapshots["15m"]
    snap_5m = snapshots["5m"]

    # Étape 1 — Régime
    regime_result = detect_regime(snap_1h, prev_snapshot_1h)
    if not regime_result.tradeable:
        return CascadeResult(
            symbol=symbol,
            regime=regime_result.regime,
            cascade_passed=False,
            score=0.0,
            quality=SignalQuality.REJECTED,
            active_setup=None,
            scores_by_tf={},
            rejection_reason="regime_not_tradeable",
            evaluated_at_ms=now_ms,
        )

    # Étape 2 — Score 4h
    s4h = _score_4h(snap_4h)
    if s4h < 0.60:
        return _reject("4h_score_too_low", {"4h": s4h})

    # Étape 3 — Score 1h
    s1h = _score_1h(snap_1h)
    if s1h < 0.60:
        return _reject("1h_score_too_low", {"4h": s4h, "1h": s1h})

    # Étape 4 — Setup
    setup = _select_setup(regime_result.regime, snap_15m, snap_1h)
    if setup is None:
        return _reject("no_setup_selected", {"4h": s4h, "1h": s1h})

    # Étape 5 — Scores 15m et 5m
    s15m = _score_15m(snap_15m, setup)
    s5m = _score_5m(snap_5m)

    scores_by_tf = {"4h": s4h, "1h": s1h, "15m": s15m, "5m": s5m}

    # Étape 6 — Score global pondéré
    score = (
        s4h * _WEIGHTS["4h"]
        + s1h * _WEIGHTS["1h"]
        + s15m * _WEIGHTS["15m"]
        + s5m * _WEIGHTS["5m"]
    ) / _TOTAL_WEIGHT

    quality = (
        SignalQuality.HIGH if score >= 0.75
        else SignalQuality.MEDIUM if score >= 0.60
        else SignalQuality.LOW if score >= 0.50
        else SignalQuality.REJECTED
    )
    cascade_passed = quality in (SignalQuality.HIGH, SignalQuality.MEDIUM)

    return CascadeResult(
        symbol=symbol,
        regime=regime_result.regime,
        cascade_passed=cascade_passed,
        score=score,
        quality=quality,
        active_setup=setup,
        scores_by_tf=scores_by_tf,
        rejection_reason=None if cascade_passed else "score_below_threshold",
        evaluated_at_ms=now_ms,
    )
