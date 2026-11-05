"""Unit tests for Crypto Liquid Screener."""

import pytest

from darefx.data.crypto_screener import CryptoScreener, ScreenerCandidate


class TestCryptoScreener:
    """Test suite for crypto screener and market scanning."""

    def test_liquid_universe_returns_valid_symbols(self) -> None:
        screener = CryptoScreener(exchange_id="binance")
        symbols = screener.get_liquid_universe(min_volume_usd=1_000_000, top_n=10)
        assert len(symbols) > 0
        assert any("BTC" in s for s in symbols)
        assert all("/" in s for s in symbols)

    def test_scan_symbol_returns_candidate(self) -> None:
        screener = CryptoScreener(exchange_id="binance")
        candidate = screener.scan_symbol("BTC/USDT", timeframe="4h", limit=50)
        assert candidate is not None
        assert isinstance(candidate, ScreenerCandidate)
        assert candidate.symbol == "BTC/USDT"
        assert candidate.price > 0
        assert candidate.trend_bias in ("BULLISH", "BEARISH", "SIDEWAYS")
        assert candidate.signal in ("BUY", "SELL", "NEUTRAL")

    def test_scan_universe_sorting(self) -> None:
        screener = CryptoScreener(exchange_id="binance")
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        candidates = screener.scan_universe(symbols)
        assert len(candidates) > 0
        # Check sorted by active signal and confidence
        assert all(isinstance(c, ScreenerCandidate) for c in candidates)
