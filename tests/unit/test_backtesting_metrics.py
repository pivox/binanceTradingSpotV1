"""Unit tests — BacktestMetrics computation (Phase 2)."""

from __future__ import annotations

import pytest

from tradebot.services.backtesting.metrics import compute_metrics
from tradebot.services.backtesting.models import BacktestTrade


def _trade(
    pnl_r: float | None,
    exit_reason: str | None = "TP",
    mfe: float = 1.0,
    mae: float = 0.5,
) -> BacktestTrade:
    return BacktestTrade(
        symbol="BTCUSDC",
        entry_time_ms=1_000_000,
        entry_price=50_000.0,
        stop_loss=49_000.0,
        take_profit=51_500.0,
        sl_method="PIVOT",
        exit_time_ms=2_000_000 if exit_reason != "OPEN" else None,
        exit_price=(51_500.0 if pnl_r and pnl_r > 0 else 49_000.0)
        if exit_reason != "OPEN"
        else None,
        exit_reason=exit_reason,  # type: ignore[arg-type]
        pnl_r=pnl_r,
        mfe_pct=mfe,
        mae_pct=mae,
        signal_score=75,
        signal_context={},
    )


class TestComputeMetrics:
    def test_empty_trades(self):
        m = compute_metrics([])
        assert m.total_trades == 0
        assert m.closed_trades == 0
        assert m.passes_phase_gate is False

    def test_only_open_trades(self):
        m = compute_metrics([_trade(None, "OPEN")])
        assert m.total_trades == 1
        assert m.closed_trades == 0
        assert m.winrate == 0.0
        assert m.passes_phase_gate is False

    def test_perfect_results_pass_gate(self):
        trades = [_trade(1.5, "TP") for _ in range(10)]
        m = compute_metrics(trades)
        assert m.winrate == 1.0
        assert m.profit_factor == float("inf")
        assert m.passes_phase_gate is True

    def test_all_losses_fail_gate(self):
        trades = [_trade(-1.0, "SL") for _ in range(10)]
        m = compute_metrics(trades)
        assert m.winning_trades == 0
        assert m.winrate == 0.0
        assert m.profit_factor == 0.0
        assert m.passes_phase_gate is False

    def test_60pct_winrate(self):
        wins = [_trade(1.5, "TP") for _ in range(6)]
        losses = [_trade(-1.0, "SL") for _ in range(4)]
        m = compute_metrics(wins + losses)
        assert m.winrate == pytest.approx(0.6)
        assert m.profit_factor == pytest.approx(9.0 / 4.0)
        assert m.passes_phase_gate is True

    def test_expectancy(self):
        # E = (6 × 1.5 + 4 × -1.0) / 10 = 0.5
        wins = [_trade(1.5, "TP") for _ in range(6)]
        losses = [_trade(-1.0, "SL") for _ in range(4)]
        m = compute_metrics(wins + losses)
        assert m.expectancy_r == pytest.approx(0.5)

    def test_max_drawdown_sequential_losses(self):
        # 5 losses then 5 wins → peak drawdown = 5R × 1% = 5%
        trades = [_trade(-1.0, "SL") for _ in range(5)] + [
            _trade(1.5, "TP") for _ in range(5)
        ]
        m = compute_metrics(trades, risk_pct=0.01)
        assert m.max_drawdown_pct == pytest.approx(5.0)

    def test_max_drawdown_recovers(self):
        # Win, then 3 losses, then win → peak drawdown = 3R
        trades = [
            _trade(1.5, "TP"),
            _trade(-1.0, "SL"),
            _trade(-1.0, "SL"),
            _trade(-1.0, "SL"),
            _trade(1.5, "TP"),
        ]
        m = compute_metrics(trades, risk_pct=0.01)
        assert m.max_drawdown_pct == pytest.approx(3.0)

    def test_gate_fails_winrate_below_50(self):
        wins = [_trade(1.5, "TP") for _ in range(4)]
        losses = [_trade(-1.0, "SL") for _ in range(6)]
        m = compute_metrics(wins + losses)
        assert m.winrate == pytest.approx(0.4)
        assert m.passes_phase_gate is False

    def test_gate_fails_pf_below_1_3(self):
        # 51% winrate but TP = 0.9R → PF = (51 × 0.9) / (49 × 1.0) < 1.3
        wins = [_trade(0.9, "TP") for _ in range(51)]
        losses = [_trade(-1.0, "SL") for _ in range(49)]
        m = compute_metrics(wins + losses)
        assert m.winrate > 0.50
        assert m.profit_factor < 1.3
        assert m.passes_phase_gate is False

    def test_gate_fails_drawdown_above_15(self):
        # 16 consecutive losses × 1% risk = 16% drawdown
        trades = [_trade(-1.0, "SL") for _ in range(16)] + [
            _trade(1.5, "TP") for _ in range(20)
        ]
        m = compute_metrics(trades, risk_pct=0.01)
        assert m.max_drawdown_pct >= 15.0
        assert m.passes_phase_gate is False

    def test_avg_mfe_mae(self):
        trades = [_trade(1.5, "TP", mfe=3.0, mae=0.8) for _ in range(4)]
        m = compute_metrics(trades)
        assert m.avg_mfe_pct == pytest.approx(3.0)
        assert m.avg_mae_pct == pytest.approx(0.8)

    def test_closed_count_excludes_open(self):
        trades = [_trade(1.5, "TP")] * 3 + [_trade(None, "OPEN")] * 2
        m = compute_metrics(trades)
        assert m.total_trades == 5
        assert m.closed_trades == 3


class TestVerdict:
    def test_inconclusive_below_min(self):
        from tradebot.services.backtesting.models import Verdict

        trades = [_trade(1.5, "TP") for _ in range(10)]
        m = compute_metrics(trades, min_closed_trades=20)
        assert m.verdict == Verdict.INCONCLUSIVE
        assert len(m.verdict_reasons) == 1
        assert "10" in m.verdict_reasons[0]

    def test_inconclusive_empty(self):
        from tradebot.services.backtesting.models import Verdict

        m = compute_metrics([], min_closed_trades=20)
        assert m.verdict == Verdict.INCONCLUSIVE

    def test_pass_when_all_criteria_met(self):
        from tradebot.services.backtesting.models import Verdict

        wins = [_trade(1.5, "TP") for _ in range(14)]
        losses = [_trade(-1.0, "SL") for _ in range(6)]
        m = compute_metrics(wins + losses, min_closed_trades=20)
        assert m.verdict == Verdict.PASS
        assert m.verdict_reasons == []

    def test_fail_low_winrate(self):
        from tradebot.services.backtesting.models import Verdict

        wins = [_trade(1.5, "TP") for _ in range(8)]
        losses = [_trade(-1.0, "SL") for _ in range(12)]
        m = compute_metrics(wins + losses, min_closed_trades=20)
        assert m.verdict == Verdict.FAIL
        assert any("winrate" in r.lower() or "Winrate" in r for r in m.verdict_reasons)

    def test_fail_low_profit_factor(self):
        from tradebot.services.backtesting.models import Verdict

        wins = [_trade(0.9, "TP") for _ in range(51)]
        losses = [_trade(-1.0, "SL") for _ in range(49)]
        m = compute_metrics(wins + losses, min_closed_trades=20)
        assert m.verdict == Verdict.FAIL
        assert any("factor" in r.lower() or "Factor" in r for r in m.verdict_reasons)

    def test_fail_high_drawdown(self):
        from tradebot.services.backtesting.models import Verdict

        losses = [_trade(-1.0, "SL") for _ in range(16)]
        wins = [_trade(1.5, "TP") for _ in range(20)]
        m = compute_metrics(losses + wins, risk_pct=0.01, min_closed_trades=20)
        assert m.verdict == Verdict.FAIL
        assert any(
            "drawdown" in r.lower() or "Drawdown" in r for r in m.verdict_reasons
        )

    def test_passes_phase_gate_still_set(self):
        wins = [_trade(1.5, "TP") for _ in range(14)]
        losses = [_trade(-1.0, "SL") for _ in range(6)]
        m = compute_metrics(wins + losses, min_closed_trades=20)
        assert m.passes_phase_gate is True
