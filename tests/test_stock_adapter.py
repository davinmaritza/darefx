"""Unit tests for StockAdapter (Alpaca / Equities)."""

import pytest

from darefx.trading.mt5_bridge import OrderType
from darefx.trading.stock_adapter import StockAdapter, StockCredentials


class TestStockAdapter:
    """Test suite for equities execution adapter."""

    def test_simulation_mode_initialization(self) -> None:
        adapter = StockAdapter(credentials=StockCredentials(simulation_mode=True))
        assert adapter.is_connected
        assert adapter.is_simulation

    def test_account_info_in_simulation(self) -> None:
        adapter = StockAdapter(credentials=StockCredentials(simulation_mode=True))
        acc = adapter.get_account_info()
        assert acc.currency == "USD"
        assert acc.balance == 25_000.0
        assert acc.equity == 25_000.0
        assert acc.free_margin == 25_000.0

    def test_simulation_order_flow(self) -> None:
        adapter = StockAdapter(credentials=StockCredentials(simulation_mode=True))

        # 1. Place Market Buy Order (e.g. 10 shares NVDA)
        res = adapter.send_market_order("NVDA", OrderType.BUY, volume=10.0)
        assert res.success
        assert res.ticket > 0
        assert res.volume == 10.0
        assert res.price > 0.0

        # 2. Check Holdings
        positions = adapter.get_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos.symbol == "NVDA"
        assert pos.volume == 10.0
        assert pos.order_type == OrderType.BUY

        # 3. Liquidate / Close
        closed = adapter.close_position(res.ticket)
        assert closed

        # 4. Positions empty
        assert len(adapter.get_positions()) == 0

    def test_invalid_volume_rejected(self) -> None:
        adapter = StockAdapter(credentials=StockCredentials(simulation_mode=True))
        res = adapter.send_market_order("AAPL", OrderType.BUY, volume=0.0)
        assert not res.success
