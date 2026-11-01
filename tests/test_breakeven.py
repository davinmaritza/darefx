"""Unit tests for Break-Even (BEP) protection and News Filter trade guard."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest

from darefx.risk.circuit_breaker import CircuitBreaker
from darefx.risk.news_filter import EconomicNewsFilter, EconomicEvent
from darefx.trading.executor import ExecutionConfig, OrderExecutor
from darefx.trading.mt5_bridge import MT5Bridge, MT5Credentials, OrderType, Position


class TestBreakEvenAndNewsGuard:
    """Tests for automated Move SL to Break-Even and News Filter trade guard."""

    def test_breakeven_trigger_for_buy_position(self, tmp_path):
        state_file = tmp_path / "mt5_sim.json"
        risk_file = tmp_path / "risk_sim.json"

        bridge = MT5Bridge(
            credentials=MT5Credentials(simulation_mode=True),
            state_file=state_file,
        )
        bridge.connect()

        # Open a BUY position at 1.08000
        bridge.send_market_order("EURUSD", "BUY", 0.10, sl=1.07500, tp=1.09000, current_price=1.08000)
        positions = bridge.get_open_positions("EURUSD")
        assert len(positions) == 1
        pos = positions[0]

        circuit = CircuitBreaker(state_file=risk_file)
        config = ExecutionConfig(breakeven_trigger_pips=15.0, breakeven_buffer_pips=1.0)
        executor = OrderExecutor(bridge=bridge, circuit_breaker=circuit, config=config)

        # 1. Price at 1.08100 (+10 pips) -> Should NOT trigger BEP yet (< 15 pips)
        pos.current_price = 1.08100
        updated = executor.check_and_apply_breakeven("EURUSD")
        assert len(updated) == 0
        assert pos.sl == 1.07500

        # 2. Price at 1.08160 (+16 pips) -> Should TRIGGER BEP!
        pos.current_price = 1.08160
        updated = executor.check_and_apply_breakeven("EURUSD")
        assert len(updated) == 1
        assert updated[0]["ticket"] == pos.ticket
        assert updated[0]["action"] == "BUY"
        assert updated[0]["new_sl"] == pytest.approx(1.08010, 0.00001)
        assert pos.sl == pytest.approx(1.08010, 0.00001)

        # 3. Second run while price is still high -> Should NOT re-modify (already protected)
        updated_again = executor.check_and_apply_breakeven("EURUSD")
        assert len(updated_again) == 0

    def test_breakeven_trigger_for_sell_position(self, tmp_path):
        state_file = tmp_path / "mt5_sim_sell.json"
        risk_file = tmp_path / "risk_sim_sell.json"

        bridge = MT5Bridge(
            credentials=MT5Credentials(simulation_mode=True),
            state_file=state_file,
        )
        bridge.connect()

        # Open a SELL position at 1.09000
        bridge.send_market_order("EURUSD", "SELL", 0.10, sl=1.09500, tp=1.08000, current_price=1.09000)
        positions = bridge.get_open_positions("EURUSD")
        assert len(positions) == 1
        pos = positions[0]

        circuit = CircuitBreaker(state_file=risk_file)
        config = ExecutionConfig(breakeven_trigger_pips=15.0, breakeven_buffer_pips=1.0)
        executor = OrderExecutor(bridge=bridge, circuit_breaker=circuit, config=config)

        # Price drops to 1.08820 (+18 pips in profit for SELL)
        pos.current_price = 1.08820
        updated = executor.check_and_apply_breakeven("EURUSD")
        assert len(updated) == 1
        assert updated[0]["action"] == "SELL"
        # Safe SL: entry (1.09000) - 1 pip buffer (0.0001) = 1.08990
        assert updated[0]["new_sl"] == pytest.approx(1.08990, 0.00001)
        assert pos.sl == pytest.approx(1.08990, 0.00001)

    def test_execute_signal_blocked_by_news_freeze(self, tmp_path):
        state_file = tmp_path / "mt5_sim_news.json"
        risk_file = tmp_path / "risk_sim_news.json"

        bridge = MT5Bridge(
            credentials=MT5Credentials(simulation_mode=True),
            state_file=state_file,
        )
        bridge.connect()

        circuit = CircuitBreaker(state_file=risk_file)
        news_svc = EconomicNewsFilter()

        # Inject upcoming high impact event happening in 10 minutes
        event_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        news_svc._cached_events = [
            EconomicEvent(
                title="US FOMC Statement",
                country="USD",
                date=event_time,
                impact="High",
            )
        ]
        news_svc._last_fetch_time = datetime.now(timezone.utc)

        executor = OrderExecutor(
            bridge=bridge,
            circuit_breaker=circuit,
            config=ExecutionConfig(news_filter_enabled=True),
            news_filter=news_svc,
        )

        report = executor.execute_signal(
            symbol="EURUSD",
            action="BUY",
            current_price=1.08500,
            stop_loss=1.08000,
            take_profit=1.09100,
        )

        assert report.executed is False
        assert report.status == "rejected_news_freeze"
        assert "US FOMC Statement" in report.message
