"""Unit tests for CCXT cryptocurrency exchange execution adapter."""

import pytest

from darefx.trading.ccxt_adapter import CCXTAdapter, CryptoCredentials
from darefx.trading.mt5_bridge import OrderType


class TestCCXTAdapter:
    """Test suite for CCXT execution adapter."""

    def test_simulation_mode_initialization(self) -> None:
        creds = CryptoCredentials(
            exchange_id="binance",
            api_key="",
            secret="",
            simulation_mode=True,
        )
        adapter = CCXTAdapter(credentials=creds)
        assert adapter.is_connected
        assert adapter.is_simulation

    def test_account_info_in_simulation(self) -> None:
        adapter = CCXTAdapter(credentials=CryptoCredentials(simulation_mode=True))
        acc = adapter.get_account_info()
        assert acc.currency == "USDT"
        assert acc.balance == 10_000.0
        assert acc.equity == 10_000.0
        assert acc.free_margin == 10_000.0

    def test_simulation_order_flow(self) -> None:
        adapter = CCXTAdapter(credentials=CryptoCredentials(simulation_mode=True))

        # 1. Place Buy Order
        res = adapter.send_market_order(
            symbol="BTC/USDT",
            order_type=OrderType.BUY,
            volume=0.5,
            sl=48_000.0,
            tp=55_000.0,
        )
        assert res.success
        assert res.ticket > 0
        assert res.volume == 0.5

        # 2. Check Open Positions
        positions = adapter.get_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos.symbol == "BTC/USDT"
        assert pos.order_type == OrderType.BUY
        assert pos.volume == 0.5

        # 3. Close Order
        closed = adapter.close_position(res.ticket)
        assert closed

        # 4. Verify Positions Empty
        assert len(adapter.get_positions()) == 0

    def test_invalid_volume_rejected(self) -> None:
        adapter = CCXTAdapter(credentials=CryptoCredentials(simulation_mode=True))
        res = adapter.send_market_order("ETH/USDT", OrderType.BUY, volume=0.0)
        assert not res.success
