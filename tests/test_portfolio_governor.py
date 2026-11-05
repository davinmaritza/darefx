"""Unit tests for PortfolioGovernor and cross-asset risk management."""

from datetime import UTC, datetime

import pytest

from darefx.risk.portfolio_governor import (
    AssetClass,
    PortfolioGovernor,
    PortfolioGovernorConfig,
    SignalCandidate,
)
from darefx.trading.mt5_bridge import OrderType, Position


@pytest.fixture
def governor() -> PortfolioGovernor:
    config = PortfolioGovernorConfig(
        max_total_positions=3,
        max_positions_per_asset={"forex": 1, "crypto": 1, "stocks": 1},
        max_portfolio_risk_pct=3.0,
        risk_per_trade_pct=1.0,
        min_confidence_threshold=0.50,
        min_adx=20.0,
        allow_hedging=False,
    )
    return PortfolioGovernor(config=config)


def test_classify_symbol(governor: PortfolioGovernor) -> None:
    assert governor.classify_symbol("EURUSD") == AssetClass.FOREX
    assert governor.classify_symbol("GBPUSD") == AssetClass.FOREX
    assert governor.classify_symbol("BTC/USDT") == AssetClass.CRYPTO
    assert governor.classify_symbol("ETH/USDT") == AssetClass.CRYPTO
    assert governor.classify_symbol("NVDA") == AssetClass.STOCKS
    assert governor.classify_symbol("AAPL") == AssetClass.STOCKS


def test_can_open_trade_approved(governor: PortfolioGovernor) -> None:
    cand = SignalCandidate(
        asset_class=AssetClass.FOREX,
        symbol="EURUSD",
        action="BUY",
        entry_price=1.0850,
        stop_loss=1.0800,
        take_profit=1.0950,
        confidence=0.65,
        adx=28.0,
        risk_reward_ratio=2.0,
    )
    ok, reason = governor.can_open_trade(candidate=cand, current_positions=[])
    assert ok is True
    assert "Approved" in reason


def test_reject_low_confidence(governor: PortfolioGovernor) -> None:
    cand = SignalCandidate(
        asset_class=AssetClass.FOREX,
        symbol="EURUSD",
        action="BUY",
        entry_price=1.0850,
        stop_loss=1.0800,
        take_profit=1.0950,
        confidence=0.45,  # below 0.50
        adx=28.0,
    )
    ok, reason = governor.can_open_trade(candidate=cand, current_positions=[])
    assert ok is False
    assert "below threshold" in reason


def test_reject_asset_class_cap(governor: PortfolioGovernor) -> None:
    # 1 Forex already open
    active_forex = Position(
        ticket=101,
        symbol="GBPUSD",
        order_type=OrderType.BUY,
        volume=0.1,
        open_price=1.2800,
        current_price=1.2810,
        sl=1.2750,
        tp=1.2900,
        profit=10.0,
        open_time=datetime.now(UTC),
    )
    cand = SignalCandidate(
        asset_class=AssetClass.FOREX,
        symbol="EURUSD",
        action="BUY",
        entry_price=1.0850,
        stop_loss=1.0800,
        take_profit=1.0950,
        confidence=0.65,
        adx=25.0,
    )
    ok, reason = governor.can_open_trade(candidate=cand, current_positions=[active_forex])
    assert ok is False
    assert "Asset cap for FOREX reached" in reason


def test_reject_duplicate_symbol(governor: PortfolioGovernor) -> None:
    active_btc = Position(
        ticket=102,
        symbol="BTC/USDT",
        order_type=OrderType.BUY,
        volume=0.01,
        open_price=68000.0,
        current_price=68500.0,
        sl=66000.0,
        tp=72000.0,
        profit=5.0,
        open_time=datetime.now(UTC),
    )
    cand = SignalCandidate(
        asset_class=AssetClass.CRYPTO,
        symbol="BTC/USDT",
        action="BUY",
        entry_price=68500.0,
        stop_loss=67000.0,
        take_profit=71000.0,
        confidence=0.75,
        adx=30.0,
    )
    ok, reason = governor.can_open_trade(candidate=cand, current_positions=[active_btc])
    assert ok is False
    assert "already open" in reason


def test_rank_and_filter(governor: PortfolioGovernor) -> None:
    c1 = SignalCandidate(
        asset_class=AssetClass.FOREX,
        symbol="EURUSD",
        action="BUY",
        entry_price=1.0850,
        stop_loss=1.0800,
        take_profit=1.0950,
        confidence=0.60,
        adx=25.0,
        risk_reward_ratio=2.0,
    )
    c2 = SignalCandidate(
        asset_class=AssetClass.CRYPTO,
        symbol="BTC/USDT",
        action="BUY",
        entry_price=68000.0,
        stop_loss=66000.0,
        take_profit=72000.0,
        confidence=0.85,
        adx=35.0,
        risk_reward_ratio=2.0,
    )
    c3 = SignalCandidate(
        asset_class=AssetClass.STOCKS,
        symbol="NVDA",
        action="BUY",
        entry_price=135.0,
        stop_loss=130.0,
        take_profit=145.0,
        confidence=0.70,
        adx=28.0,
        risk_reward_ratio=2.0,
    )
    c4 = SignalCandidate(
        asset_class=AssetClass.CRYPTO,
        symbol="ETH/USDT",
        action="BUY",
        entry_price=2600.0,
        stop_loss=2500.0,
        take_profit=2800.0,
        confidence=0.55,
        adx=22.0,
        risk_reward_ratio=2.0,
    )

    approved = governor.rank_and_filter([c1, c2, c3, c4], current_positions=[])
    # Total cap is 3, per-asset cap is 1
    # BTC/USDT (0.85) -> approved (crypto slot used)
    # NVDA (0.70) -> approved (stocks slot used)
    # EURUSD (0.60) -> approved (forex slot used)
    # ETH/USDT (0.55) -> rejected because crypto cap 1 reached
    assert len(approved) == 3
    symbols = [a.symbol for a in approved]
    assert symbols == ["BTC/USDT", "NVDA", "EURUSD"]
