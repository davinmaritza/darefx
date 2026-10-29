"""Unit tests for DareFX backtest engine and performance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from darefx.backtest.engine import BacktestConfig, BacktestEngine
from darefx.backtest.metrics import calculate_metrics


class TestMetrics:
    """Tests for institutional performance metrics."""

    def test_calculate_metrics_winning_portfolio(self):
        dates = pd.date_range("2023-01-01", periods=252, freq="B", tz="UTC")
        # Steady 20% gain over 1 year
        equity = pd.Series(np.linspace(10000, 12000, 252), index=dates)
        trade_pnls = [100.0, -50.0, 150.0, -30.0, 200.0]

        metrics = calculate_metrics(equity, trade_pnls)

        assert metrics.initial_balance == 10000.0
        assert metrics.final_balance == 12000.0
        assert metrics.total_return_pct == pytest.approx(20.0, 0.1)
        assert metrics.sharpe_ratio > 1.0
        assert metrics.sortino_ratio > 1.0
        assert metrics.max_drawdown_pct == 0.0  # Monotonically increasing
        assert metrics.win_rate_pct == pytest.approx(60.0, 0.1)  # 3 wins out of 5 trades
        assert metrics.profit_factor > 1.0


class TestBacktestEngine:
    """Tests for trade execution and friction simulation."""

    def test_backtest_execution_with_friction(self):
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")

        # Create trending upward data
        closes = np.linspace(1.0800, 1.1200, n)
        highs = closes + 0.0030
        lows = closes - 0.0030
        opens = closes - 0.0005

        # Strong buy predictions
        prob_buy = np.full(n, 0.65)
        prob_sell = np.full(n, 0.15)
        prob_neutral = np.full(n, 0.20)

        df_oos = pd.DataFrame(
            {
                "timestamp": dates,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "atr_14": np.full(n, 0.0050),
                "prob_buy": prob_buy,
                "prob_sell": prob_sell,
                "prob_neutral": prob_neutral,
            }
        )

        config = BacktestConfig(
            initial_capital=10000.0,
            risk_per_trade_pct=1.0,
            spread_pips=1.5,
            slippage_pips=1.0,
            confidence_threshold=0.50,
        )

        engine = BacktestEngine(config=config)
        result = engine.run(df_oos)

        assert not result.trade_log.empty
        assert result.metrics.total_trades > 0
        assert len(result.equity_curve) > 0

        # Verify transaction friction was recorded for every trade
        for _, trade in result.trade_log.iterrows():
            assert trade["friction_cost_usd"] > 0.0
            assert trade["net_pnl_usd"] < trade["gross_pnl_usd"]  # Friction reduces gross PnL
