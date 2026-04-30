"""Unit tests — MTF Validator (Phase 1b).

Toutes les fonctions testées ici sont pures (aucun accès DB).
Format snapshots : payload_json tel que produit par factory.py.
"""
from __future__ import annotations

import pytest

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
from tradebot.services.mtf.validator import ValidationProfile, TfProfile, load_profile, validate


# ── Helpers snapshot ──────────────────────────────────────────────────────────

def _av(value: float) -> dict:
    return {"status": "available", "value": value}


def _unavail(reason: str = "warmup") -> dict:
    return {"status": "unavailable", "reason": reason}


def _macd_block(hist: float, macd_val: float = 1.0, sig: float = 0.5) -> dict:
    """Format namespaced produit par factory._namespace_available."""
    return {
        "macd": _av(macd_val),
        "signal": _av(sig),
        "hist": _av(hist),
    }


def _snap_4h(
    close: float = 50000.0,
    ema20: float = 49000.0,
    ema50: float = 47000.0,
    ema200: float = 42000.0,
    rsi: float = 58.0,
    atr: float = 500.0,
    macd_hist: float = 100.0,
) -> dict:
    return {
        "close_price": close,
        "ema20": _av(ema20),
        "ema50": _av(ema50),
        "ema200": _av(ema200),
        "rsi": _av(rsi),
        "atr": _av(atr),
        "macd": _macd_block(hist=macd_hist),
    }


def _snap_1h(
    close: float = 50000.0,
    ema20: float = 49500.0,
    ema50: float = 48000.0,
    rsi: float = 52.0,
    atr: float = 200.0,
    adx: float = 28.0,
    macd_hist: float = 50.0,
) -> dict:
    return {
        "close_price": close,
        "ema20": _av(ema20),
        "ema50": _av(ema50),
        "rsi": _av(rsi),
        "atr": _av(atr),
        "adx": _av(adx),
        "macd": _macd_block(hist=macd_hist),
    }


def _snap_15m(
    close: float = 50000.0,
    ema20: float = 50100.0,   # ≈ 0.2% au-dessus → price_near_ema20 ✓
    ema50: float = 49000.0,
    rsi: float = 50.0,
    atr: float = 100.0,       # 100/50000 = 0.2% < 2% → atr_contracting ✓
    macd_hist: float = 20.0,
) -> dict:
    return {
        "close_price": close,
        "ema20": _av(ema20),
        "ema50": _av(ema50),
        "rsi": _av(rsi),
        "atr": _av(atr),
        "macd": _macd_block(hist=macd_hist),
    }


def _snap_5m(
    close: float = 50000.0,
    ema50: float = 48000.0,
    macd_hist: float = 10.0,
) -> dict:
    return {
        "close_price": close,
        "ema50": _av(ema50),
        "macd": _macd_block(hist=macd_hist),
    }


def _full_snapshots() -> dict:
    return {
        "4h": _snap_4h(),
        "1h": _snap_1h(),
        "15m": _snap_15m(),
        "5m": _snap_5m(),
    }


def _default_profile() -> ValidationProfile:
    return ValidationProfile(
        name="regular",
        context_tfs={
            "4h": TfProfile(
                conditions=["ema20_above_ema50", "ema50_above_ema200", "rsi_between_45_70", "macd_hist_positive"],
                score_max=40,
            ),
            "1h": TfProfile(
                conditions=["price_above_ema20", "adx_gt_25", "macd_hist_positive_or_rising"],
                score_max=30,
            ),
            "15m": TfProfile(
                conditions=["rsi_between_40_60", "price_near_ema20", "atr_contracting"],
                score_max=30,
            ),
        },
        trigger_tf="5m",
        trigger_conditions=["macd_hist_turning_positive", "close_above_recent_high"],
        blocking_filters=[
            "rsi_4h_gt_75",
            "price_4h_gt_ema20_plus_2atr",
            "adx_1h_lt_20",
            "macd_1h_hist_negative_and_falling",
        ],
        threshold=60,
    )


# ── Conditions atomiques 4h ───────────────────────────────────────────────────

class TestConditions4h:
    def test_ema20_above_ema50_true(self) -> None:
        assert ema20_above_ema50({"ema20": _av(105.0), "ema50": _av(100.0)}) is True

    def test_ema20_above_ema50_false(self) -> None:
        assert ema20_above_ema50({"ema20": _av(95.0), "ema50": _av(100.0)}) is False

    def test_ema20_above_ema50_unavailable(self) -> None:
        assert ema20_above_ema50({"ema20": _unavail(), "ema50": _av(100.0)}) is False

    def test_ema50_above_ema200_true(self) -> None:
        assert ema50_above_ema200({"ema50": _av(47000.0), "ema200": _av(42000.0)}) is True

    def test_ema50_above_ema200_false(self) -> None:
        assert ema50_above_ema200({"ema50": _av(40000.0), "ema200": _av(42000.0)}) is False

    def test_rsi_between_45_70_inside(self) -> None:
        assert rsi_between_45_70({"rsi": _av(58.0)}) is True

    def test_rsi_between_45_70_below(self) -> None:
        assert rsi_between_45_70({"rsi": _av(44.0)}) is False

    def test_rsi_between_45_70_above(self) -> None:
        assert rsi_between_45_70({"rsi": _av(71.0)}) is False

    def test_rsi_between_45_70_on_boundary(self) -> None:
        assert rsi_between_45_70({"rsi": _av(45.0)}) is True
        assert rsi_between_45_70({"rsi": _av(70.0)}) is True

    def test_macd_hist_positive_true(self) -> None:
        assert macd_hist_positive({"macd": _macd_block(hist=5.0)}) is True

    def test_macd_hist_positive_false(self) -> None:
        assert macd_hist_positive({"macd": _macd_block(hist=-3.0)}) is False

    def test_macd_hist_positive_unavailable(self) -> None:
        assert macd_hist_positive({"macd": {"hist": _unavail()}}) is False


# ── Conditions atomiques 1h ───────────────────────────────────────────────────

class TestConditions1h:
    def test_price_above_ema20_true(self) -> None:
        snap = {"close_price": 101.0, "ema20": _av(100.0)}
        assert price_above_ema20(snap) is True

    def test_price_above_ema20_false(self) -> None:
        snap = {"close_price": 99.0, "ema20": _av(100.0)}
        assert price_above_ema20(snap) is False

    def test_price_above_ema20_no_close(self) -> None:
        assert price_above_ema20({"ema20": _av(100.0)}) is False

    def test_adx_gt_25_true(self) -> None:
        assert adx_gt_25({"adx": _av(28.0)}) is True

    def test_adx_gt_25_false(self) -> None:
        assert adx_gt_25({"adx": _av(24.0)}) is False

    def test_adx_gt_25_exact_boundary(self) -> None:
        assert adx_gt_25({"adx": _av(25.0)}) is False  # strict >

    def test_macd_hist_positive_or_rising_positive(self) -> None:
        snap = {"macd": _macd_block(hist=2.0)}
        assert macd_hist_positive_or_rising(snap) is True

    def test_macd_hist_positive_or_rising_with_prev_rising(self) -> None:
        snap = {"macd": _macd_block(hist=-1.0)}
        prev = {"macd": _macd_block(hist=-3.0)}
        assert macd_hist_positive_or_rising(snap, prev) is True

    def test_macd_hist_positive_or_rising_falling(self) -> None:
        snap = {"macd": _macd_block(hist=-3.0)}
        prev = {"macd": _macd_block(hist=-1.0)}
        assert macd_hist_positive_or_rising(snap, prev) is False

    def test_macd_hist_positive_or_rising_no_prev_negative(self) -> None:
        snap = {"macd": _macd_block(hist=-1.0)}
        assert macd_hist_positive_or_rising(snap, None) is False


# ── Conditions atomiques 15m ─────────────────────────────────────────────────

class TestConditions15m:
    def test_rsi_between_40_60_inside(self) -> None:
        assert rsi_between_40_60({"rsi": _av(50.0)}) is True

    def test_rsi_between_40_60_below(self) -> None:
        assert rsi_between_40_60({"rsi": _av(39.0)}) is False

    def test_rsi_between_40_60_above(self) -> None:
        assert rsi_between_40_60({"rsi": _av(61.0)}) is False

    def test_price_near_ema20_within_tolerance(self) -> None:
        # |50000 - 50100| / 50100 ≈ 0.2% < 1.5%
        snap = {"close_price": 50000.0, "ema20": _av(50100.0)}
        assert price_near_ema20(snap) is True

    def test_price_near_ema20_too_far(self) -> None:
        # |50000 - 52000| / 52000 ≈ 3.8% > 1.5%
        snap = {"close_price": 50000.0, "ema20": _av(52000.0)}
        assert price_near_ema20(snap) is False

    def test_price_near_ema20_no_close(self) -> None:
        assert price_near_ema20({"ema20": _av(100.0)}) is False

    def test_atr_contracting_with_prev(self) -> None:
        snap = {"atr": _av(100.0), "close_price": 50000.0}
        prev = {"atr": _av(150.0)}
        assert atr_contracting(snap, prev) is True

    def test_atr_contracting_expanding_with_prev(self) -> None:
        snap = {"atr": _av(200.0), "close_price": 50000.0}
        prev = {"atr": _av(150.0)}
        assert atr_contracting(snap, prev) is False

    def test_atr_contracting_no_prev_low_ratio(self) -> None:
        # 100/50000 = 0.2% < 2%
        snap = {"atr": _av(100.0), "close_price": 50000.0}
        assert atr_contracting(snap, None) is True

    def test_atr_contracting_no_prev_high_ratio(self) -> None:
        # 1500/50000 = 3% > 2%
        snap = {"atr": _av(1500.0), "close_price": 50000.0}
        assert atr_contracting(snap, None) is False


# ── Trigger 5m ───────────────────────────────────────────────────────────────

class TestTrigger5m:
    def test_macd_hist_turning_positive_with_prev(self) -> None:
        snap = {"macd": _macd_block(hist=1.0)}
        prev = {"macd": _macd_block(hist=-2.0)}
        assert macd_hist_turning_positive(snap, prev) is True

    def test_macd_hist_turning_positive_already_was_positive(self) -> None:
        snap = {"macd": _macd_block(hist=2.0)}
        prev = {"macd": _macd_block(hist=1.0)}
        assert macd_hist_turning_positive(snap, prev) is False

    def test_macd_hist_turning_positive_no_prev_fallback(self) -> None:
        snap = {"macd": _macd_block(hist=1.0)}
        assert macd_hist_turning_positive(snap, None) is True

    def test_macd_hist_turning_positive_negative_no_trigger(self) -> None:
        snap = {"macd": _macd_block(hist=-1.0)}
        assert macd_hist_turning_positive(snap, None) is False

    def test_close_above_recent_high_true(self) -> None:
        snap = {"close_price": 50000.0, "ema50": _av(48000.0)}
        assert close_above_recent_high(snap) is True

    def test_close_above_recent_high_false(self) -> None:
        snap = {"close_price": 47000.0, "ema50": _av(48000.0)}
        assert close_above_recent_high(snap) is False


# ── Filtres bloquants ─────────────────────────────────────────────────────────

class TestBlockingFilters:
    def test_rsi_4h_gt_75_blocks(self) -> None:
        snaps = {"4h": {"rsi": _av(76.0)}}
        assert rsi_4h_gt_75(snaps) is True

    def test_rsi_4h_gt_75_no_block(self) -> None:
        snaps = {"4h": {"rsi": _av(65.0)}}
        assert rsi_4h_gt_75(snaps) is False

    def test_price_4h_gt_ema20_plus_2atr_blocks(self) -> None:
        # close=53000, ema20=50000, atr=1000 → ema20+2*atr=52000 < 53000
        snaps = {"4h": {"close_price": 53000.0, "ema20": _av(50000.0), "atr": _av(1000.0)}}
        assert price_4h_gt_ema20_plus_2atr(snaps) is True

    def test_price_4h_gt_ema20_plus_2atr_no_block(self) -> None:
        # close=51000, ema20=50000, atr=1000 → ema20+2*atr=52000 > 51000
        snaps = {"4h": {"close_price": 51000.0, "ema20": _av(50000.0), "atr": _av(1000.0)}}
        assert price_4h_gt_ema20_plus_2atr(snaps) is False

    def test_price_4h_gt_ema20_plus_2atr_missing_atr(self) -> None:
        snaps = {"4h": {"close_price": 53000.0, "ema20": _av(50000.0)}}
        assert price_4h_gt_ema20_plus_2atr(snaps) is False

    def test_adx_1h_lt_20_blocks(self) -> None:
        snaps = {"1h": {"adx": _av(18.0)}}
        assert adx_1h_lt_20(snaps) is True

    def test_adx_1h_lt_20_no_block(self) -> None:
        snaps = {"1h": {"adx": _av(22.0)}}
        assert adx_1h_lt_20(snaps) is False

    def test_macd_1h_hist_negative_and_falling_blocks(self) -> None:
        snaps = {"1h": {"macd": _macd_block(hist=-3.0)}}
        prev = {"1h": {"macd": _macd_block(hist=-1.0)}}
        assert macd_1h_hist_negative_and_falling(snaps, prev) is True

    def test_macd_1h_hist_negative_and_rising_no_block(self) -> None:
        snaps = {"1h": {"macd": _macd_block(hist=-1.0)}}
        prev = {"1h": {"macd": _macd_block(hist=-3.0)}}
        assert macd_1h_hist_negative_and_falling(snaps, prev) is False

    def test_macd_1h_hist_positive_no_block(self) -> None:
        snaps = {"1h": {"macd": _macd_block(hist=2.0)}}
        assert macd_1h_hist_negative_and_falling(snaps, None) is False

    def test_macd_1h_hist_negative_no_prev_no_block(self) -> None:
        snaps = {"1h": {"macd": _macd_block(hist=-2.0)}}
        assert macd_1h_hist_negative_and_falling(snaps, None) is False


# ── validate() ───────────────────────────────────────────────────────────────

class TestValidate:
    def test_valid_signal_all_conditions_pass(self) -> None:
        result = validate("BTCUSDC", _full_snapshots(), _default_profile())
        assert result.valid is True
        assert result.score == 100
        assert result.trend_4h is True
        assert result.trend_1h is True
        assert result.structure_15m is True
        assert result.trigger_5m is True
        assert result.blocking_filter is None

    def test_symbol_preserved(self) -> None:
        result = validate("SOLUSDC", _full_snapshots(), _default_profile())
        assert result.symbol == "SOLUSDC"

    def test_profile_preserved(self) -> None:
        result = validate("BTCUSDC", _full_snapshots(), _default_profile())
        assert result.profile == "regular"

    def test_evaluated_at_ms_is_recent(self) -> None:
        import time
        before = int(time.time() * 1000)
        result = validate("BTCUSDC", _full_snapshots(), _default_profile())
        after = int(time.time() * 1000)
        assert before <= result.evaluated_at_ms <= after

    def test_missing_4h_snapshot_returns_invalid(self) -> None:
        snaps = {k: v for k, v in _full_snapshots().items() if k != "4h"}
        result = validate("BTCUSDC", snaps, _default_profile())
        assert result.valid is False
        assert result.blocking_filter == "missing_snapshot_4h"

    def test_missing_5m_snapshot_returns_invalid(self) -> None:
        snaps = {k: v for k, v in _full_snapshots().items() if k != "5m"}
        result = validate("BTCUSDC", snaps, _default_profile())
        assert result.valid is False
        assert result.blocking_filter == "missing_snapshot_5m"

    def test_blocking_filter_rsi_4h_prevents_valid(self) -> None:
        snaps = {**_full_snapshots(), "4h": _snap_4h(rsi=80.0)}
        result = validate("BTCUSDC", snaps, _default_profile())
        assert result.valid is False
        assert result.blocking_filter == "rsi_4h_gt_75"

    def test_blocking_filter_adx_1h_prevents_valid(self) -> None:
        snaps = {**_full_snapshots(), "1h": _snap_1h(adx=15.0)}
        result = validate("BTCUSDC", snaps, _default_profile())
        assert result.valid is False
        assert result.blocking_filter == "adx_1h_lt_20"

    def test_blocking_filter_still_evaluates_conditions(self) -> None:
        snaps = {**_full_snapshots(), "4h": _snap_4h(rsi=80.0)}
        result = validate("BTCUSDC", snaps, _default_profile())
        # Les conditions 4h sont quand même évaluées (sauf le filtre RSI > 75
        # qui affecte valid mais les conditions ema/macd restent calculées)
        assert "4h" in result.context_json

    def test_score_below_threshold_invalid(self) -> None:
        # 4h conditions all fail → score_4h=0, total=60 (1h=30 + 15m=30)
        # But all 1h and 15m pass → score=60 which equals threshold. Let's fail more.
        # Fail 2 conditions in 4h (20 pts lost) → score=80 still above 60
        # Fail all 4h → score_4h=0 → total=60 (at threshold, valid=True if trigger)
        # Need to fail some 1h/15m too
        bad_4h = _snap_4h(ema20=45000.0)  # ema20 < ema50 → fails ema20_above_ema50
        bad_1h = _snap_1h(adx=20.0, macd_hist=-5.0)  # fails adx_gt_25 and macd_hist_*
        snaps = {**_full_snapshots(), "4h": bad_4h, "1h": bad_1h}
        result = validate("BTCUSDC", snaps, _default_profile())
        # 4h: ema20_above_ema50=False(0), ema50_above_ema200=True(10), rsi=True(10), macd=True(10) → 30
        # 1h: price_above_ema20=True(10), adx_gt_25=False(0), macd_hist_*=False(0) → 10
        # 15m: all pass → 30
        # total = 70 ≥ 60 → still valid if trigger fires
        # Let's also fail 15m RSI
        bad_15m = _snap_15m(rsi=35.0, atr=1500.0)  # rsi fails, atr_contracting fails
        snaps = {**snaps, "15m": bad_15m}
        result = validate("BTCUSDC", snaps, _default_profile())
        # 15m: rsi=False, price_near_ema20=True, atr=False → score_15m=10
        # total = 30 + 10 + 10 = 50 < 60 → invalid
        assert result.valid is False
        assert result.score < 60

    def test_score_above_threshold_with_trigger_is_valid(self) -> None:
        # ema20=49500 < ema50=49800 → ema20_above_ema50 fails (score_4h=30)
        # price_4h_gt_ema20_plus_2atr: 50000 vs 49500+2*500=50500 → no block ✓
        bad_4h = _snap_4h(close=50000.0, ema20=49500.0, ema50=49800.0, atr=500.0)
        snaps = {**_full_snapshots(), "4h": bad_4h}
        result = validate("BTCUSDC", snaps, _default_profile())
        # 4h: 3/4 pass → 30 pts ; 1h: 30 ; 15m: 30 → total=90 ≥ 60
        assert result.score == 90
        assert result.valid is True

    def test_no_trigger_makes_invalid(self) -> None:
        # 5m: close < ema50 (close_above_recent_high fails)
        # 5m: macd_hist negative (macd_hist_turning_positive fails — hist <= 0)
        bad_5m = {"close_price": 46000.0, "ema50": _av(48000.0), "macd": _macd_block(hist=-1.0)}
        snaps = {**_full_snapshots(), "5m": bad_5m}
        result = validate("BTCUSDC", snaps, _default_profile())
        assert result.trigger_5m is False
        assert result.valid is False
        assert result.score == 100  # score is still computed

    def test_context_json_contains_all_timeframes(self) -> None:
        result = validate("BTCUSDC", _full_snapshots(), _default_profile())
        assert "4h" in result.context_json
        assert "1h" in result.context_json
        assert "15m" in result.context_json
        assert "5m" in result.context_json
        assert "scores" in result.context_json

    def test_context_scores_sum_correctly(self) -> None:
        result = validate("BTCUSDC", _full_snapshots(), _default_profile())
        scores = result.context_json["scores"]
        assert scores["total"] == scores["4h"] + scores["1h"] + scores["15m"]
        assert scores["total"] == result.score

    def test_context_json_condition_names_present(self) -> None:
        result = validate("BTCUSDC", _full_snapshots(), _default_profile())
        assert "ema20_above_ema50" in result.context_json["4h"]
        assert "price_above_ema20" in result.context_json["1h"]
        assert "rsi_between_40_60" in result.context_json["15m"]


# ── load_profile() ────────────────────────────────────────────────────────────

class TestLoadProfile:
    def test_loads_regular_profile(self) -> None:
        profile = load_profile()
        assert profile.name == "regular"

    def test_context_tfs_present(self) -> None:
        profile = load_profile()
        assert set(profile.context_tfs.keys()) == {"4h", "1h", "15m"}

    def test_4h_conditions_and_score(self) -> None:
        profile = load_profile()
        tf = profile.context_tfs["4h"]
        assert tf.score_max == 40
        assert "ema20_above_ema50" in tf.conditions
        assert "macd_hist_positive" in tf.conditions

    def test_1h_conditions_and_score(self) -> None:
        profile = load_profile()
        tf = profile.context_tfs["1h"]
        assert tf.score_max == 30
        assert "adx_gt_25" in tf.conditions

    def test_15m_conditions_and_score(self) -> None:
        profile = load_profile()
        tf = profile.context_tfs["15m"]
        assert tf.score_max == 30
        assert "atr_contracting" in tf.conditions

    def test_trigger_tf_is_5m(self) -> None:
        profile = load_profile()
        assert profile.trigger_tf == "5m"

    def test_blocking_filters_present(self) -> None:
        profile = load_profile()
        assert "rsi_4h_gt_75" in profile.blocking_filters
        assert "adx_1h_lt_20" in profile.blocking_filters

    def test_threshold_is_60(self) -> None:
        profile = load_profile()
        assert profile.threshold == 60

    def test_validate_with_loaded_profile(self) -> None:
        profile = load_profile()
        result = validate("BTCUSDC", _full_snapshots(), profile)
        assert result.valid is True
