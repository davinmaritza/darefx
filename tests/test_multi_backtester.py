"""Unit and integration tests for MultiAssetBacktester and CLI backtest-multi."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from darefx.analysis.multi_backtester import (
    MultiAssetBacktestConfig,
    MultiAssetBacktester,
    MultiAssetBacktestResult,
)
from darefx.cli import app


def test_multi_backtester_runs_and_produces_metrics() -> None:
    """Test that MultiAssetBacktester runs across all asset classes and returns metrics."""
    config = MultiAssetBacktestConfig(
        start_date="2024-01-01",
        end_date="2024-04-01",
        initial_equity=10_000.0,
        forex_symbols=["EURUSD", "GBPUSD"],
        crypto_symbols=["BTC/USDT", "ETH/USDT"],
        stock_symbols=["AAPL", "NVDA"],
        max_total_positions=4,
    )
    backtester = MultiAssetBacktester(config=config)
    res = backtester.run()

    assert isinstance(res, MultiAssetBacktestResult)
    assert res.initial_equity == 10_000.0
    assert res.final_equity > 0.0
    assert not res.equity_curve.empty
    assert "date" in res.equity_curve.columns
    assert "equity" in res.equity_curve.columns
    assert "drawdown_pct" in res.equity_curve.columns

    # Verify governor constraint: open positions never exceeded max_total_positions
    max_open = res.equity_curve["open_positions"].max()
    assert max_open <= config.max_total_positions

    # Asset breakdown verified
    assert "forex" in res.asset_breakdown
    assert "crypto" in res.asset_breakdown
    assert "stocks" in res.asset_breakdown
    assert res.asset_breakdown["forex"].asset_class == "FOREX"

    # Correlation matrix verified
    assert "forex" in res.correlation_matrix
    assert "crypto" in res.correlation_matrix["forex"]
    assert res.correlation_matrix["forex"]["forex"] == 1.0


def test_multi_backtester_zero_trades_graceful() -> None:
    """Test edge case where short timeframe has minimal movements."""
    config = MultiAssetBacktestConfig(
        start_date="2024-01-01",
        end_date="2024-01-10",  # Under warm-up period
        initial_equity=5_000.0,
    )
    backtester = MultiAssetBacktester(config=config)
    res = backtester.run()

    assert res.initial_equity == 5_000.0
    assert res.final_equity == 5_000.0
    assert res.total_trades == 0
    assert res.overall_win_rate == 0.0


def test_cli_backtest_multi_invocation(tmp_path: pytest.TempPathFactory) -> None:
    """Test CLI backtest-multi command executes and outputs formatted summary."""
    runner = CliRunner()
    csv_out = str(tmp_path / "equity_curve.csv")

    result = runner.invoke(
        app,
        [
            "backtest-multi",
            "--start",
            "2024-01-01",
            "--end",
            "2024-03-01",
            "--equity",
            "10000",
            "--export-csv",
            csv_out,
        ],
    )
    assert result.exit_code == 0
    assert "DareFX Multi-Asset Portfolio Performance" in result.stdout
    assert "Performance by Asset Class" in result.stdout
    assert "Cross-Asset Daily Return Correlation" in result.stdout
