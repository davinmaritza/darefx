"""Unit tests for MultiScheduler cross-asset trading coordinator."""

import pytest

from darefx.risk.portfolio_governor import (
    AssetClass,
    PortfolioGovernor,
    PortfolioGovernorConfig,
    SignalCandidate,
)
from darefx.trading.ccxt_adapter import CCXTAdapter
from darefx.trading.mt5_bridge import MT5Bridge
from darefx.trading.multi_scheduler import MultiScheduler, MultiSchedulerConfig
from darefx.trading.stock_adapter import StockAdapter


@pytest.fixture
def mock_scheduler() -> MultiScheduler:
    config = MultiSchedulerConfig(
        forex_symbols=["EURUSD"],
        crypto_symbols=["BTC/USDT"],
        stock_symbols=["NVDA"],
        account_equity=10_000.0,
        execute_orders=False,
    )
    mt5 = MT5Bridge()
    ccxt = CCXTAdapter()
    stock = StockAdapter()
    governor = PortfolioGovernor(
        config=PortfolioGovernorConfig(
            max_total_positions=5,
            max_positions_per_asset={"forex": 2, "crypto": 2, "stocks": 2},
            min_confidence_threshold=0.30,
        )
    )
    return MultiScheduler(
        config=config,
        mt5_bridge=mt5,
        ccxt_adapter=ccxt,
        stock_adapter=stock,
        governor=governor,
    )


def test_scheduler_init(mock_scheduler: MultiScheduler) -> None:
    assert mock_scheduler.config.forex_symbols == ["EURUSD"]
    assert mock_scheduler.config.crypto_symbols == ["BTC/USDT"]
    assert mock_scheduler.config.stock_symbols == ["NVDA"]
    assert mock_scheduler.is_running is False


def test_get_all_active_positions(mock_scheduler: MultiScheduler) -> None:
    positions = mock_scheduler.get_all_active_positions()
    assert isinstance(positions, list)


def test_execute_candidate_simulated(mock_scheduler: MultiScheduler) -> None:
    cand = SignalCandidate(
        asset_class=AssetClass.CRYPTO,
        symbol="BTC/USDT",
        action="BUY",
        entry_price=68000.0,
        stop_loss=66000.0,
        take_profit=72000.0,
        confidence=0.75,
    )
    result = mock_scheduler.execute_candidate(cand)
    assert result["symbol"] == "BTC/USDT"
    assert result["status"] == "simulated"
    assert result["action"] == "BUY"


def test_execute_candidate_live(mock_scheduler: MultiScheduler) -> None:
    mock_scheduler.config.execute_orders = True
    cand = SignalCandidate(
        asset_class=AssetClass.STOCKS,
        symbol="AAPL",
        action="BUY",
        entry_price=220.0,
        stop_loss=215.0,
        take_profit=230.0,
        confidence=0.70,
    )
    result = mock_scheduler.execute_candidate(cand)
    assert result["symbol"] == "AAPL"
    assert result["status"] in ("executed", "simulated")
    assert result["ticket"] > 0


def test_run_all_cycles(mock_scheduler: MultiScheduler) -> None:
    results = mock_scheduler.run_all_cycles()
    assert "forex" in results
    assert "crypto" in results
    assert "stocks" in results
    assert isinstance(results["forex"], list)
    assert isinstance(results["crypto"], list)
    assert isinstance(results["stocks"], list)


def test_scheduler_lifecycle(mock_scheduler: MultiScheduler) -> None:
    mock_scheduler.start()
    assert mock_scheduler.is_running is True
    mock_scheduler.stop()
    assert mock_scheduler.is_running is False
