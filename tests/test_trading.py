"""Tests for DareFX Trading Module: MT5 Bridge, Order Executor, and TradingBot."""

from __future__ import annotations

from pathlib import Path
import pytest

from darefx.risk.circuit_breaker import CircuitBreaker, CircuitState
from darefx.trading.bot import BotConfig, TradingBot
from darefx.trading.executor import ExecutionConfig, OrderExecutor
from darefx.trading.mt5_bridge import MT5Bridge, MT5Credentials, OrderType


class TestMT5Bridge:
    """Test suite for MT5 bridge adapter in simulation / paper trading mode."""

    def test_simulation_connect_and_account_info(self) -> None:
        creds = MT5Credentials(login=123456, server="Valetax-Demo", simulation_mode=True)
        bridge = MT5Bridge(credentials=creds)

        assert not bridge.is_connected
        assert bridge.connect()
        assert bridge.is_connected

        account = bridge.get_account_info()
        assert account.login == 123456
        assert account.currency == "USD"
        assert account.balance == 10_000.0
        assert account.equity == 10_000.0
        assert account.leverage == 100.0

    def test_simulation_send_market_order_and_query_positions(self) -> None:
        creds = MT5Credentials(simulation_mode=True)
        bridge = MT5Bridge(credentials=creds)
        bridge.connect()

        result = bridge.send_market_order(
            symbol="EURUSD",
            action=OrderType.BUY,
            volume=0.15,
            sl=1.08000,
            tp=1.09500,
            current_price=1.08500,
            comment="test_buy",
        )

        assert result.success
        assert result.ticket > 0
        assert result.volume == 0.15
        assert result.price == 1.08500

        # Query open positions
        positions = bridge.get_positions(symbol="EURUSD")
        assert len(positions) == 1
        pos = positions[0]
        assert pos.ticket == result.ticket
        assert pos.symbol == "EURUSD"
        assert pos.order_type == OrderType.BUY
        assert pos.volume == 0.15
        assert pos.sl == 1.08000
        assert pos.tp == 1.09500

    def test_simulation_close_position(self) -> None:
        creds = MT5Credentials(simulation_mode=True)
        bridge = MT5Bridge(credentials=creds)
        bridge.connect()

        order_res = bridge.send_market_order(
            symbol="EURUSD",
            action=OrderType.BUY,
            volume=0.10,
            sl=1.08000,
            tp=1.09500,
            current_price=1.08500,
        )
        assert len(bridge.get_positions()) == 1

        # Close position at profit (1.08700 = +20 pips)
        close_res = bridge.close_position(ticket=order_res.ticket, close_price=1.08700)
        assert close_res.success
        assert len(bridge.get_positions()) == 0

        # Balance should increase by 20 pips * $10/pip * 0.10 lots = +$20.00
        account = bridge.get_account_info()
        assert account.balance == 10_020.0


class TestOrderExecutor:
    """Test suite for pre-trade constraints and execution dispatcher."""

    def test_execute_signal_success(self, tmp_path: Path) -> None:
        bridge = MT5Bridge(credentials=MT5Credentials(simulation_mode=True))
        bridge.connect()
        cb = CircuitBreaker(state_file=tmp_path / "cb.json")
        cb.update(current_equity=10_000.0, current_date_str="2026-10-29")

        executor = OrderExecutor(bridge=bridge, circuit_breaker=cb, config=ExecutionConfig(risk_pct=1.0))
        report = executor.execute_signal(
            symbol="EURUSD",
            action="BUY",
            current_price=1.08500,
            stop_loss=1.08000,  # 50 pips risk
            take_profit=1.09100,
            current_spread_pips=1.5,
        )

        assert report.executed
        assert report.status == "executed"
        assert report.ticket > 0
        assert report.lots > 0.0
        assert report.entry_price == 1.08500

    def test_execute_signal_blocked_by_circuit_breaker(self, tmp_path: Path) -> None:
        bridge = MT5Bridge(credentials=MT5Credentials(simulation_mode=True))
        bridge.connect()
        cb = CircuitBreaker(state_file=tmp_path / "cb.json")
        # Trigger shutdown
        cb.update(current_equity=10_000.0, current_date_str="2026-10-29")
        cb.update(current_equity=8_000.0, current_date_str="2026-10-29")

        executor = OrderExecutor(bridge=bridge, circuit_breaker=cb)
        report = executor.execute_signal(
            symbol="EURUSD",
            action="BUY",
            current_price=1.08500,
            stop_loss=1.08000,
            take_profit=1.09100,
        )

        assert not report.executed
        assert report.status == "rejected_circuit_breaker"
        assert "SHUTDOWN" in report.message

    def test_execute_signal_blocked_by_high_spread(self, tmp_path: Path) -> None:
        bridge = MT5Bridge(credentials=MT5Credentials(simulation_mode=True))
        bridge.connect()
        cb = CircuitBreaker(state_file=tmp_path / "cb.json")
        cb.update(current_equity=10_000.0, current_date_str="2026-10-29")

        executor = OrderExecutor(bridge=bridge, circuit_breaker=cb, config=ExecutionConfig(max_spread_pips=2.5))
        report = executor.execute_signal(
            symbol="EURUSD",
            action="BUY",
            current_price=1.08500,
            stop_loss=1.08000,
            take_profit=1.09100,
            current_spread_pips=3.5,  # Exceeds 2.5
        )

        assert not report.executed
        assert report.status == "rejected_high_spread"


class TestTradingBot:
    """Test suite for daily trading bot execution loop."""

    def test_bot_daily_cycle_execution(self) -> None:
        config = BotConfig(
            symbol="EURUSD",
            model_path="data/models/lightgbm_eurusd.joblib",
            data_dir="data/processed",
            confidence_threshold=0.46,
            adx_min=32.0,
            execute_orders=True,
        )
        bot = TradingBot(config=config)
        result = bot.run_daily_cycle(current_equity=10_000.0)

        # Result status must be one of the handled paths
        assert result["status"] in ("signal_dispatched", "filtered_by_regime", "no_signal", "blocked_by_circuit_breaker")
