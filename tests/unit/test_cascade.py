"""Unit tests for cascade validation (evaluate_cascade + regime detection)."""
from __future__ import annotations

import pytest

from tradebot.domain.models.cascade_result import MarketRegime
from tradebot.domain.models.signal import SignalQuality, SetupType
from tradebot.services.mtf.cascade import evaluate_cascade
from tradebot.services.mtf.regime import detect_regime


# ── Snapshot builders ─────────────────────────────────────────────────────────

def _av(value: float) -> dict:
    return {"status": "available", "value": value}


def _adx_av(value: float, plus_di: float = 30.0, minus_di: float = 10.0) -> dict:
    return {"status": "available", "value": value, "plus_di": plus_di, "minus_di": minus_di}


def _macd_av(value: float = 1.0, signal: float = 0.5, histogram: float = 0.5) -> dict:
    return {"status": "available", "value": value, "signal": signal, "histogram": histogram}


def _bb_av(bandwidth: float = 0.02, upper: float = 110.0, middle: float = 100.0, lower: float = 90.0) -> dict:
    return {"status": "available", "bandwidth": bandwidth, "upper": upper, "middle": middle, "lower": lower}


def _sr_av(k: float = 0.2, d: float = 0.1) -> dict:
    return {"status": "available", "k": k, "d": d}


def _trending_up_1h(close: float = 100.0) -> dict:
    return {
        "close_price": close,
        "ema20": _av(105.0),
        "ema50": _av(100.0),
        "ema200": _av(90.0),
        "adx": _adx_av(30.0),
        "rsi": _av(58.0),
        "macd": _macd_av(),
        "vwap": _av(close - 1),
        "bollinger": _bb_av(bandwidth=0.05),
        "stoch_rsi": _sr_av(),
    }


def _strong_4h() -> dict:
    return {
        "close_price": 100.0,
        "ema20": _av(105.0),
        "ema50": _av(100.0),
        "ema200": _av(90.0),
        "adx": _adx_av(28.0),
        "rsi": _av(55.0),
        "macd": _macd_av(),
        "bollinger": _bb_av(),
        "stoch_rsi": _sr_av(),
    }


def _pullback_15m(close: float = 102.0) -> dict:
    """Price sitting between EMA20 and EMA50 — Setup A conditions."""
    return {
        "close_price": close,
        "ema20": _av(103.0),
        "ema50": _av(100.0),
        "ema200": _av(90.0),
        "adx": _adx_av(26.0),
        "rsi": _av(50.0),
        "macd": _macd_av(),
        "bollinger": _bb_av(),
        "pivots": {"status": "available", "pp": 105.0, "s1": 98.0, "s2": 95.0, "r1": 110.0},
        "stoch_rsi": _sr_av(),
        "volume_ratio": 1.2,
    }


def _bullish_5m() -> dict:
    return {
        "close_price": 102.0,
        "ema9": _av(101.5),
        "adx": _adx_av(22.0),
        "rsi": _av(54.0),
        "macd": _macd_av(),
        "bollinger": _bb_av(),
        "stoch_rsi": _sr_av(k=0.25, d=0.10),
        "volume_ratio": 1.5,
    }


def _full_snapshots() -> dict:
    return {
        "4h": _strong_4h(),
        "1h": _trending_up_1h(),
        "15m": _pullback_15m(),
        "5m": _bullish_5m(),
    }


# ── detect_regime ─────────────────────────────────────────────────────────────

class TestDetectRegime:
    def test_trending_up_when_ema_aligned_and_adx_high(self) -> None:
        snap = _trending_up_1h()
        result = detect_regime(snap)
        assert result.regime == MarketRegime.TRENDING_UP
        assert result.tradeable is True

    def test_trending_down_when_ema_inverted_and_adx_high(self) -> None:
        snap = {
            **_trending_up_1h(),
            "ema20": _av(85.0),
            "ema50": _av(90.0),
            "ema200": _av(100.0),
            "adx": _adx_av(30.0, plus_di=5.0, minus_di=30.0),
        }
        result = detect_regime(snap)
        assert result.regime == MarketRegime.TRENDING_DOWN
        assert result.tradeable is False

    def test_ranging_when_adx_low(self) -> None:
        snap = {**_trending_up_1h(), "adx": _adx_av(15.0)}
        result = detect_regime(snap)
        assert result.regime == MarketRegime.RANGING
        assert result.tradeable is True

    def test_volatile_when_atr_high(self) -> None:
        snap = {**_trending_up_1h(), "atr": _av(5.0), "close_price": 100.0}
        result = detect_regime(snap)
        assert result.regime == MarketRegime.VOLATILE
        assert result.tradeable is False

    def test_recovery_on_golden_cross(self) -> None:
        prev = {**_trending_up_1h(), "ema20": _av(99.0), "ema50": _av(100.0)}
        curr = {**_trending_up_1h(), "ema20": _av(101.0), "ema50": _av(100.0), "adx": _adx_av(15.0)}
        result = detect_regime(curr, prev)
        assert result.regime == MarketRegime.RECOVERY
        assert result.golden_cross_detected is True

    def test_no_golden_cross_without_prev_snapshot(self) -> None:
        snap = _trending_up_1h()
        result = detect_regime(snap, prev_snapshot_1h=None)
        assert result.golden_cross_detected is False


# ── evaluate_cascade ──────────────────────────────────────────────────────────

class TestEvaluateCascade:
    def test_passes_with_all_bullish_conditions(self) -> None:
        result = evaluate_cascade("BTCUSDC", _full_snapshots())
        assert result.cascade_passed is True
        assert result.quality in (SignalQuality.HIGH, SignalQuality.MEDIUM)
        assert result.score >= 0.60

    def test_rejects_when_4h_snapshot_missing(self) -> None:
        snaps = {k: v for k, v in _full_snapshots().items() if k != "4h"}
        result = evaluate_cascade("BTCUSDC", snaps)
        assert result.cascade_passed is False
        assert "missing_snapshot_4h" in (result.rejection_reason or "")

    def test_rejects_when_4h_score_too_low(self) -> None:
        snaps = {
            **_full_snapshots(),
            "4h": {
                "close_price": 80.0,
                "ema20": _av(80.0),   # price NOT above EMA50
                "ema50": _av(100.0),
                "adx": _adx_av(10.0),
                "rsi": _av(30.0),
                "macd": {"status": "unavailable", "reason": "warmup"},
                "bollinger": _bb_av(),
                "stoch_rsi": _sr_av(),
            },
        }
        result = evaluate_cascade("BTCUSDC", snaps)
        assert result.cascade_passed is False
        assert result.rejection_reason == "4h_score_too_low"

    def test_rejects_when_regime_not_tradeable(self) -> None:
        volatile_1h = {
            **_trending_up_1h(),
            "atr": _av(5.0),
            "close_price": 100.0,
        }
        snaps = {**_full_snapshots(), "1h": volatile_1h}
        result = evaluate_cascade("BTCUSDC", snaps)
        assert result.cascade_passed is False
        assert result.rejection_reason == "regime_not_tradeable"

    def test_scores_by_tf_populated_on_pass(self) -> None:
        result = evaluate_cascade("BTCUSDC", _full_snapshots())
        assert result.cascade_passed is True
        assert set(result.scores_by_tf.keys()) >= {"4h", "1h", "15m", "5m"}
        for score in result.scores_by_tf.values():
            assert 0.0 <= score <= 1.0

    def test_setup_a_selected_in_trending_pullback(self) -> None:
        result = evaluate_cascade("BTCUSDC", _full_snapshots())
        if result.cascade_passed:
            assert result.active_setup == SetupType.A

    def test_high_quality_when_score_above_75(self) -> None:
        result = evaluate_cascade("BTCUSDC", _full_snapshots())
        if result.score >= 0.75:
            assert result.quality == SignalQuality.HIGH
        elif result.score >= 0.60:
            assert result.quality == SignalQuality.MEDIUM

    def test_symbol_preserved_in_result(self) -> None:
        result = evaluate_cascade("SOLUSDC", _full_snapshots())
        assert result.symbol == "SOLUSDC"

    def test_evaluated_at_ms_is_recent(self) -> None:
        import time
        before = int(time.time() * 1000)
        result = evaluate_cascade("BTCUSDC", _full_snapshots())
        after = int(time.time() * 1000)
        assert before <= result.evaluated_at_ms <= after
