"""Unit tests for StockScreener."""

import pytest

from darefx.data.crypto_screener import ScreenerCandidate
from darefx.data.stock_screener import StockScreener


class TestStockScreener:
    """Test suite for equities market scanner."""

    def test_liquid_universe_returns_sp500_symbols(self) -> None:
        screener = StockScreener()
        symbols = screener.get_liquid_universe(top_n=10)
        assert len(symbols) == 10
        assert "NVDA" in symbols
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_scan_symbol_returns_valid_candidate(self) -> None:
        screener = StockScreener()
        cand = screener.scan_symbol("NVDA")
        assert isinstance(cand, ScreenerCandidate)
        assert cand.symbol == "NVDA"
        assert cand.price > 100.0
        assert cand.signal in ("BUY", "SELL", "NEUTRAL")
        assert cand.trend_bias in ("BULLISH", "BEARISH", "SIDEWAYS")
        assert cand.confidence > 0.5

    def test_scan_universe_sorting(self) -> None:
        screener = StockScreener()
        candidates = screener.scan_universe(["NVDA", "MSFT", "AAPL"])
        assert len(candidates) == 3
        assert candidates[0].signal != "NEUTRAL"
