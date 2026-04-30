"""MTF Validator — Phase 1b.

Fonction pure validate() : aucun accès DB, testable sans infrastructure.
Le profil de conditions est chargé depuis un YAML (validations.regular.yaml).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from tradebot.domain.models.mtf_signal import MTFSignal
from tradebot.services.mtf._validator_conditions import (
    adx_1h_lt_20,
    adx_gt_25,
    atr_contracting,
    close_above_recent_high,
    ema20_above_ema50,
    ema50_above_ema200,
    macd_1h_hist_negative_and_falling,
    macd_hist_positive,
    macd_hist_positive_or_rising,
    macd_hist_turning_positive,
    price_4h_gt_ema20_plus_2atr,
    price_above_ema20,
    price_near_ema20,
    rsi_4h_gt_75,
    rsi_between_40_60,
    rsi_between_45_70,
)

_DEFAULT_PROFILE_PATH = Path(__file__).parents[4] / "config" / "validations.regular.yaml"

_CONDITION_REGISTRY: dict[str, Callable[[dict, dict | None], bool]] = {
    "ema20_above_ema50": ema20_above_ema50,
    "ema50_above_ema200": ema50_above_ema200,
    "rsi_between_45_70": rsi_between_45_70,
    "macd_hist_positive": macd_hist_positive,
    "price_above_ema20": price_above_ema20,
    "adx_gt_25": adx_gt_25,
    "macd_hist_positive_or_rising": macd_hist_positive_or_rising,
    "rsi_between_40_60": rsi_between_40_60,
    "price_near_ema20": price_near_ema20,
    "atr_contracting": atr_contracting,
    "macd_hist_turning_positive": macd_hist_turning_positive,
    "close_above_recent_high": close_above_recent_high,
}

_BLOCKING_REGISTRY: dict[
    str, Callable[[dict[str, dict], dict[str, dict] | None], bool]
] = {
    "rsi_4h_gt_75": rsi_4h_gt_75,
    "price_4h_gt_ema20_plus_2atr": price_4h_gt_ema20_plus_2atr,
    "adx_1h_lt_20": adx_1h_lt_20,
    "macd_1h_hist_negative_and_falling": macd_1h_hist_negative_and_falling,
}


@dataclass(frozen=True)
class TfProfile:
    conditions: list[str]
    score_max: int


@dataclass(frozen=True)
class ValidationProfile:
    name: str
    context_tfs: dict[str, TfProfile]   # "4h", "1h", "15m"
    trigger_tf: str                      # "5m"
    trigger_conditions: list[str]        # any_of
    blocking_filters: list[str]
    threshold: int


def load_profile(path: Path | str | None = None) -> ValidationProfile:
    resolved = Path(path) if path else _DEFAULT_PROFILE_PATH
    with resolved.open() as fh:
        data = yaml.safe_load(fh)

    context_tfs: dict[str, TfProfile] = {}
    for tf, tf_data in data["context"].items():
        context_tfs[str(tf)] = TfProfile(
            conditions=tf_data["long"]["all_of"],
            score_max=int(tf_data["score_max"]),
        )

    trigger_data = data["trigger"]
    trigger_tf = str(next(iter(trigger_data)))
    trigger_conditions: list[str] = trigger_data[trigger_tf]["long"]["any_of"]

    return ValidationProfile(
        name=data["profile"],
        context_tfs=context_tfs,
        trigger_tf=trigger_tf,
        trigger_conditions=trigger_conditions,
        blocking_filters=data["blocking_filters"],
        threshold=int(data["threshold"]),
    )


def _eval_tf(
    conditions: list[str],
    score_max: int,
    snap: dict[str, Any],
    prev_snap: dict[str, Any] | None,
) -> tuple[dict[str, bool], int]:
    n = len(conditions)
    results: dict[str, bool] = {}
    for name in conditions:
        fn = _CONDITION_REGISTRY[name]
        results[name] = fn(snap, prev_snap)
    # Proportionnel : garantit que score == score_max quand toutes les conditions passent,
    # quelle que soit la divisibilité de score_max par n.
    score = int(score_max * sum(results.values()) / n) if n else 0
    return results, score


def validate(
    symbol: str,
    snapshots: dict[str, dict[str, Any]],
    profile: ValidationProfile,
    prev_snapshots: dict[str, dict[str, Any]] | None = None,
) -> MTFSignal:
    """Évalue le signal MTF — fonction pure, aucun accès DB."""
    now_ms = int(time.time() * 1000)
    context: dict[str, Any] = {}
    prev = prev_snapshots or {}

    # Vérification des snapshots requis
    required_tfs = list(profile.context_tfs.keys()) + [profile.trigger_tf]
    for tf in required_tfs:
        if snapshots.get(tf) is None:
            context["error"] = f"missing_snapshot_{tf}"
            return MTFSignal(
                symbol=symbol, profile=profile.name,
                trend_4h=False, trend_1h=False, structure_15m=False, trigger_5m=False,
                score=0, valid=False, blocking_filter=f"missing_snapshot_{tf}",
                context_json=context, evaluated_at_ms=now_ms,
            )

    # Filtres bloquants (évalués avant conditions mais n'empêchent pas leur calcul)
    active_filter: str | None = None
    for fname in profile.blocking_filters:
        fn = _BLOCKING_REGISTRY[fname]
        if fn(snapshots, prev_snapshots):
            active_filter = fname
            break

    # Évaluation des conditions par timeframe
    tf_results: dict[str, dict[str, bool]] = {}
    tf_scores: dict[str, int] = {}
    for tf, tf_profile in profile.context_tfs.items():
        results, score = _eval_tf(
            tf_profile.conditions,
            tf_profile.score_max,
            snapshots[tf],
            prev.get(tf),
        )
        tf_results[tf] = results
        tf_scores[tf] = score
        context[tf] = results

    trend_4h = all(tf_results.get("4h", {}).values())
    trend_1h = all(tf_results.get("1h", {}).values())
    structure_15m = all(tf_results.get("15m", {}).values())
    score_total = sum(tf_scores.values())
    context["scores"] = {**tf_scores, "total": score_total}

    # Déclencheur 5m (any_of)
    trigger_results: dict[str, bool] = {}
    for name in profile.trigger_conditions:
        fn = _CONDITION_REGISTRY[name]
        trigger_results[name] = fn(snapshots[profile.trigger_tf], prev.get(profile.trigger_tf))
    trigger_5m = any(trigger_results.values())
    context[profile.trigger_tf] = trigger_results

    if active_filter:
        context["blocking_filter"] = active_filter

    valid = score_total >= profile.threshold and trigger_5m and active_filter is None

    return MTFSignal(
        symbol=symbol,
        profile=profile.name,
        trend_4h=trend_4h,
        trend_1h=trend_1h,
        structure_15m=structure_15m,
        trigger_5m=trigger_5m,
        score=score_total,
        valid=valid,
        blocking_filter=active_filter,
        context_json=context,
        evaluated_at_ms=now_ms,
    )
