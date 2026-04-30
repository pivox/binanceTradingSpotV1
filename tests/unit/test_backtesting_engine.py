"""Unit tests — BacktestEngine helpers (Phase 2).

Full engine integration is tested with a real DB in tests/integration/.
Here we test the pure algorithmic helper _find_as_of.
"""

from __future__ import annotations

import pytest

from tradebot.services.backtesting.engine import _find_as_of


class TestFindAsOf:
    def test_empty_returns_none(self):
        assert _find_as_of([], 1_000) is None

    def test_all_entries_after_query_returns_none(self):
        entries = [(2_000, {}), (3_000, {})]
        assert _find_as_of(entries, 1_999) is None

    def test_exact_match_first(self):
        entries = [(1_000, {"a": 1}), (2_000, {"a": 2})]
        assert _find_as_of(entries, 1_000) == 0

    def test_exact_match_middle(self):
        entries = [(1_000, {}), (2_000, {}), (3_000, {})]
        assert _find_as_of(entries, 2_000) == 1

    def test_exact_match_last(self):
        entries = [(1_000, {}), (2_000, {}), (3_000, {})]
        assert _find_as_of(entries, 3_000) == 2

    def test_between_two_entries(self):
        entries = [(1_000, {}), (2_000, {}), (3_000, {})]
        assert _find_as_of(entries, 2_500) == 1

    def test_beyond_last_entry_returns_last(self):
        entries = [(1_000, {}), (2_000, {}), (3_000, {})]
        assert _find_as_of(entries, 99_000) == 2

    def test_single_entry_match(self):
        entries = [(5_000, {"x": 1})]
        assert _find_as_of(entries, 5_000) == 0

    def test_single_entry_before(self):
        entries = [(5_000, {})]
        assert _find_as_of(entries, 4_999) is None

    def test_single_entry_after(self):
        entries = [(5_000, {})]
        assert _find_as_of(entries, 6_000) == 0

    def test_returned_value_is_correct_payload(self):
        entries = [(1_000, {"tf": "4h"}), (2_000, {"tf": "1h"}), (3_000, {"tf": "5m"})]
        idx = _find_as_of(entries, 2_500)
        assert idx is not None
        assert entries[idx][1]["tf"] == "1h"
