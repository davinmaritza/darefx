"""Unit tests for DareFX risk management, circuit breakers, and alerts."""

from __future__ import annotations

from pathlib import Path

import pytest

from darefx.notifications.telegram import TelegramNotifier
from darefx.risk.circuit_breaker import CircuitBreaker, CircuitState
from darefx.risk.position_sizing import (
    calculate_fixed_fractional_lots,
    calculate_half_kelly_fraction,
)


class TestPositionSizing:
    """Tests for position sizing calculations."""

    def test_fixed_fractional_sizing_standard(self):
        # Account: $10,000
        # Risk: 1.0% = $100
        # Entry: 1.0850, Stop: 1.0800 (50 pips)
        # Expected: $100 / (50 * $10) = 0.20 standard lots
        res = calculate_fixed_fractional_lots(
            account_equity=10_000.0,
            entry_price=1.0850,
            stop_loss_price=1.0800,
            risk_pct=1.0,
        )

        assert res.lots == 0.20
        assert res.units == 20_000.0
        assert res.stop_distance_pips == pytest.approx(50.0, 0.01)
        assert res.risk_amount_usd == pytest.approx(100.0, 0.01)

    def test_margin_limit_capping(self):
        # Very tight stop of 1 pip on $10,000 -> would require 10.0 lots ($1M units)
        # But max margin 5% on 1:100 leverage caps position to:
        # Max margin = $500 -> Max units = ($500 * 100) / 1.0800 = ~46,296 units = 0.46 lots
        res = calculate_fixed_fractional_lots(
            account_equity=10_000.0,
            entry_price=1.0800,
            stop_loss_price=1.0799,
            risk_pct=1.0,
            max_margin_pct=5.0,
            leverage=100.0,
        )
        assert res.lots <= 0.47
        assert res.margin_utilization_pct <= 5.1

    def test_half_kelly_calculation(self):
        # 57% win rate, 1.3 win/loss ratio
        # f* = (0.57 * 1.3 - 0.43) / 1.3 = (0.741 - 0.43) / 1.3 = 0.311 / 1.3 = 23.9%
        # Half-Kelly = ~12% -> Capped at max_risk_cap_pct 2.0%
        kelly = calculate_half_kelly_fraction(win_rate=0.57, win_loss_ratio=1.3, max_risk_cap_pct=2.0)
        assert kelly == 2.0

        # No edge (40% win rate, 1.0 win/loss ratio -> f* < 0 -> 0.0%)
        no_edge_kelly = calculate_half_kelly_fraction(win_rate=0.40, win_loss_ratio=1.0)
        assert no_edge_kelly == 0.0


class TestCircuitBreaker:
    """Tests for Circuit Breaker state transitions and capital protection."""

    def test_daily_loss_triggers_paused_daily(self, tmp_path: Path):
        cb = CircuitBreaker(max_daily_loss_pct=5.0, max_total_drawdown_pct=15.0, state_file=tmp_path / "cb.json")
        cb.update(current_equity=10_000.0, current_date_str="2026-10-29")
        assert cb.state == CircuitState.ACTIVE

        # Drop equity to $9,400 (-6.0% daily loss)
        status = cb.update(current_equity=9_400.0, current_date_str="2026-10-29")
        assert status.state == CircuitState.PAUSED_DAILY
        allowed, reason = cb.can_open_new_trade()
        assert not allowed
        assert "PAUSED_DAILY" in reason

        # Rollover to next day resets to ACTIVE
        status_next_day = cb.update(current_equity=9_400.0, current_date_str="2026-10-30")
        assert status_next_day.state == CircuitState.ACTIVE
        allowed, _ = cb.can_open_new_trade()
        assert allowed

    def test_drawdown_triggers_shutdown(self, tmp_path: Path):
        cb = CircuitBreaker(max_daily_loss_pct=5.0, max_total_drawdown_pct=15.0, state_file=tmp_path / "cb.json")
        cb.update(current_equity=10_000.0, current_date_str="2026-10-29")

        # Drop equity to $8,400 (-16.0% peak drawdown)
        status = cb.update(current_equity=8_400.0, current_date_str="2026-10-29")
        assert status.state == CircuitState.SHUTDOWN
        allowed, _ = cb.can_open_new_trade()
        assert not allowed

        # Date rollover does NOT reset SHUTDOWN
        status_rollover = cb.update(current_equity=8_400.0, current_date_str="2026-10-30")
        assert status_rollover.state == CircuitState.SHUTDOWN

        # Manual administrative reset clears SHUTDOWN
        cb.reset_shutdown()
        assert cb.state == CircuitState.ACTIVE


class TestTelegramNotifier:
    """Tests for Telegram notification dispatching."""

    def test_unconfigured_credentials_handled_gracefully(self):
        notifier = TelegramNotifier(bot_token="", chat_id="")
        assert not notifier.is_configured()
        # Should return False cleanly without throwing an exception
        res = notifier.notify_trade_opened("BUY", "EURUSD", 0.10, 1.0850, 1.0800, 1.0950, 0.65)
        assert res is False
