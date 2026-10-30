"""Tests for MetaApi Cloud Bridge adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from darefx.trading.metaapi_bridge import AsyncBridgeRunner, MetaApiBridge
from darefx.trading.mt5_bridge import MT5Bridge, MT5Credentials, OrderType


class TestAsyncBridgeRunner:
    """Tests for dedicated thread runner."""

    def test_run_coroutine_in_thread(self) -> None:
        runner = AsyncBridgeRunner()

        async def sample_coro() -> int:
            return 42

        result = runner.run(sample_coro(), timeout=5.0)
        assert result == 42
        runner.stop()


class TestMetaApiBridge:
    """Tests for MetaApiBridge cloud trading operations."""

    def test_connect_fails_without_credentials(self) -> None:
        bridge = MetaApiBridge(token="", account_id="")
        assert not bridge.connect()
        assert not bridge.is_connected

    def test_unconnected_methods_raise_error(self) -> None:
        bridge = MetaApiBridge(token="tok", account_id="acc")
        with pytest.raises(ConnectionError, match="MetaApiBridge is not connected"):
            bridge.get_account_info()

        with pytest.raises(ConnectionError, match="MetaApiBridge is not connected"):
            bridge.get_positions()

        with pytest.raises(ConnectionError, match="MetaApiBridge is not connected"):
            bridge.send_market_order("EURUSD", OrderType.BUY, 0.1, 1.08, 1.09)

        with pytest.raises(ConnectionError, match="MetaApiBridge is not connected"):
            bridge.close_position(12345)

    def test_mocked_metaapi_flow(self) -> None:
        bridge = MetaApiBridge(token="test_token", account_id="test_account_id")

        mock_rpc = MagicMock()
        mock_rpc.connect = AsyncMock()
        mock_rpc.wait_synchronized = AsyncMock()
        mock_rpc.close = AsyncMock()
        mock_rpc.get_account_information = AsyncMock(return_value={
            "login": 374932479,
            "currency": "USD",
            "balance": 100000.0,
            "equity": 100050.0,
            "margin": 200.0,
            "freeMargin": 99850.0,
            "leverage": 500.0,
            "server": "ValetaxIntl_Live-2",
            "type": "DEMO",
            "tradeAllowed": True,
        })
        mock_rpc.get_positions = AsyncMock(return_value=[
            {
                "id": "99001",
                "symbol": "EURUSD",
                "type": "POSITION_TYPE_BUY",
                "volume": 0.15,
                "openPrice": 1.08500,
                "currentPrice": 1.08550,
                "stopLoss": 1.08000,
                "takeProfit": 1.09500,
                "profit": 7.50,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        ])
        mock_rpc.create_market_buy_order = AsyncMock(return_value={
            "numericCode": 10009,
            "stringCode": "ERR_NO_ERROR",
            "orderId": "99002",
            "positionId": "99002",
            "message": "Order executed",
        })
        mock_rpc.close_position = AsyncMock(return_value={
            "numericCode": 10009,
            "stringCode": "ERR_NO_ERROR",
            "message": "Position closed",
        })

        mock_account = MagicMock()
        mock_account.state = "DEPLOYED"
        mock_account.wait_connected = AsyncMock()
        mock_account.get_rpc_connection = MagicMock(return_value=mock_rpc)

        mock_api_instance = MagicMock()
        mock_api_instance.metatrader_account_api.get_account = AsyncMock(return_value=mock_account)
        mock_api_instance.close = MagicMock()

        with patch("darefx.trading.metaapi_bridge.MetaApi", return_value=mock_api_instance):
            # Connect
            assert bridge.connect()
            assert bridge.is_connected

            # Account info
            info = bridge.get_account_info()
            assert info.login == 374932479
            assert info.balance == 100000.0
            assert info.equity == 100050.0
            assert info.leverage == 500.0
            assert info.is_demo is True

            # Query positions
            positions = bridge.get_positions("EURUSD")
            assert len(positions) == 1
            assert positions[0].ticket == 99001
            assert positions[0].symbol == "EURUSD"
            assert positions[0].profit == 7.50

            # Send order
            order_res = bridge.send_market_order(
                symbol="EURUSD",
                action=OrderType.BUY,
                volume=0.15,
                sl=1.08000,
                tp=1.09500,
                current_price=1.08500,
            )
            assert order_res.success
            assert order_res.ticket == 99002

            # Close position
            close_res = bridge.close_position(ticket=99001, close_price=1.08550)
            assert close_res.success

            # Disconnect
            bridge.disconnect()
            assert not bridge.is_connected


class TestMT5BridgeMetaApiDelegation:
    """Test MT5Bridge delegating to MetaApiBridge."""

    def test_mt5_bridge_initializes_and_delegates(self) -> None:
        creds = MT5Credentials(
            simulation_mode=False,
            metaapi_token="test_tok",
            metaapi_account_id="test_acc",
        )
        bridge = MT5Bridge(credentials=creds)
        assert bridge._metaapi_bridge is not None

        # Mock the internal metaapi bridge
        mock_delegate = MagicMock()
        mock_delegate.connect.return_value = True
        mock_delegate.is_connected = True
        mock_delegate.get_account_info.return_value = MagicMock(balance=50000.0)
        mock_delegate.get_positions.return_value = []
        mock_delegate.send_market_order.return_value = MagicMock(success=True, ticket=777)
        mock_delegate.close_position.return_value = MagicMock(success=True)

        bridge._metaapi_bridge = mock_delegate

        assert bridge.connect()
        mock_delegate.connect.assert_called_once()

        assert bridge.get_account_info().balance == 50000.0
        assert bridge.get_positions() == []

        res = bridge.send_market_order("EURUSD", OrderType.BUY, 0.1, 1.08, 1.09)
        assert res.success
        assert res.ticket == 777

        close_res = bridge.close_position(777)
        assert close_res.success

        bridge.disconnect()
        mock_delegate.disconnect.assert_called_once()
