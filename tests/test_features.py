"""Unit tests for DareFX feature engineering and Triple Barrier labeling."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from darefx.features.labels import TripleBarrierConfig, apply_triple_barrier
from darefx.features.technical import (
    compute_adx,
    compute_atr,
    compute_bollinger_bands,
    compute_macd,
    compute_rsi,
    compute_stochastic,
    extract_features,
    rolling_zscore,
)


@pytest.fixture
def sample_bars() -> pd.DataFrame:
    """Generate 250 daily bars of synthetic trending and oscillating price series."""
    np.random.seed(42)
    n = 250
    timestamps = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")

    returns = np.random.normal(loc=0.0002, scale=0.006, size=n)
    prices = 1.0800 * np.exp(np.cumsum(returns))

    highs = prices * (1.0 + np.abs(np.random.normal(0, 0.003, size=n)))
    lows = prices * (1.0 - np.abs(np.random.normal(0, 0.003, size=n)))
    opens = prices * (1.0 + np.random.normal(0, 0.001, size=n))

    # Invariants
    highs = np.maximum(highs, np.maximum(opens, prices))
    lows = np.minimum(lows, np.minimum(opens, prices))

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": np.random.uniform(10000, 50000, size=n),
            "tick_count": [1000] * n,
        }
    )


class TestTechnicalIndicators:
    """Tests for indicator mathematical correctness and boundary guarantees."""

    def test_rsi_bounds(self, sample_bars: pd.DataFrame):
        rsi = compute_rsi(sample_bars["close"], period=14)
        valid = rsi.dropna()
        assert (valid >= 0.0).all()
        assert (valid <= 100.0).all()

    def test_bollinger_bands_ordering(self, sample_bars: pd.DataFrame):
        upper, middle, lower, pct_b, width = compute_bollinger_bands(sample_bars["close"], period=20, num_std=2.0)
        valid_idx = upper.dropna().index
        assert (upper.loc[valid_idx] >= middle.loc[valid_idx]).all()
        assert (middle.loc[valid_idx] >= lower.loc[valid_idx]).all()
        assert (width.loc[valid_idx] > 0.0).all()

    def test_atr_positive(self, sample_bars: pd.DataFrame):
        atr, natr = compute_atr(sample_bars["high"], sample_bars["low"], sample_bars["close"], period=14)
        valid_atr = atr.dropna()
        assert (valid_atr > 0.0).all()
        assert (natr.dropna() > 0.0).all()

    def test_macd_relationship(self, sample_bars: pd.DataFrame):
        macd, signal, hist = compute_macd(sample_bars["close"], fast=12, slow=26, signal=9)
        valid_idx = hist.dropna().index
        # Verify: hist = macd - signal
        diff = (macd.loc[valid_idx] - signal.loc[valid_idx]) - hist.loc[valid_idx]
        assert np.allclose(diff.values, 0.0, atol=1e-10)

    def test_zero_lookahead_bias(self, sample_bars: pd.DataFrame):
        """CRITICAL: Indicator at bar T must never change when future bars T+1, T+2 are added."""
        half_bars = sample_bars.iloc[:150].copy()
        full_bars = sample_bars.copy()

        features_half = extract_features(half_bars, dropna=False)
        features_full = extract_features(full_bars, dropna=False)

        # Check values at index 100 in both runs
        check_cols = ["rsi_14", "macd", "atr_14", "bb_middle", "ema_21", "return_1d"]
        for col in check_cols:
            val_half = features_half.loc[100, col]
            val_full = features_full.loc[100, col]
            assert np.isclose(val_half, val_full, atol=1e-8), f"Look-ahead detected in {col}"


class TestTripleBarrierLabeling:
    """Tests for Marcos López de Prado Triple Barrier target generation."""

    def test_profit_barrier_hit(self):
        """Simulate a deterministic strong upward breakout: must trigger +1 (profit target)."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, freq="B", tz="UTC"),
                "open": [1.0800, 1.0820, 1.0900, 1.0950, 1.1000, 1.1050, 1.1100, 1.1150, 1.1200, 1.1250],
                "high": [1.0810, 1.0890, 1.0980, 1.1020, 1.1080, 1.1120, 1.1180, 1.1220, 1.1280, 1.1300],
                "low":  [1.0790, 1.0810, 1.0880, 1.0930, 1.0980, 1.1030, 1.1080, 1.1130, 1.1180, 1.1230],
                "close":[1.0800, 1.0880, 1.0970, 1.1010, 1.1070, 1.1110, 1.1170, 1.1210, 1.1270, 1.1290],
                "atr_14": [0.0050] * 10,  # 50 pips volatility -> PT = +75 pips = 1.0875
            }
        )
        labeled = apply_triple_barrier(df, config=TripleBarrierConfig(pt_multiplier=1.5, sl_multiplier=1.5, max_holding_bars=3))
        # At bar 0 (close 1.0800), upper barrier is 1.0875. Bar 1 high is 1.0890 -> hit!
        assert labeled.loc[0, "barrier_target"] == 1
        assert labeled.loc[0, "barrier_touch_type"] == "profit_target"

    def test_stop_loss_barrier_hit(self):
        """Simulate a deterministic strong downward crash: must trigger -1 (stop loss)."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, freq="B", tz="UTC"),
                "open": [1.1000, 1.0900, 1.0800, 1.0700, 1.0600, 1.0500, 1.0400, 1.0300, 1.0200, 1.0100],
                "high": [1.1010, 1.0920, 1.0820, 1.0720, 1.0620, 1.0520, 1.0420, 1.0320, 1.0220, 1.0120],
                "low":  [1.0980, 1.0850, 1.0750, 1.0650, 1.0550, 1.0450, 1.0350, 1.0250, 1.0150, 1.0050],
                "close":[1.1000, 1.0860, 1.0760, 1.0660, 1.0560, 1.0460, 1.0360, 1.0260, 1.0160, 1.0060],
                "atr_14": [0.0050] * 10,  # SL = -75 pips = 1.0925
            }
        )
        labeled = apply_triple_barrier(df, config=TripleBarrierConfig(pt_multiplier=1.5, sl_multiplier=1.5, max_holding_bars=3))
        assert labeled.loc[0, "barrier_target"] == -1
        assert labeled.loc[0, "barrier_touch_type"] == "stop_loss"

    def test_vertical_barrier_expiry(self):
        """Simulate a dead flat market: must trigger 0 (time expiry)."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, freq="B", tz="UTC"),
                "open": [1.0800] * 10,
                "high": [1.0805] * 10,
                "low":  [1.0795] * 10,
                "close":[1.0800] * 10,
                "atr_14": [0.0050] * 10,  # Barriers at 1.0875 and 1.0725 -> neither hit in flat market
            }
        )
        labeled = apply_triple_barrier(df, config=TripleBarrierConfig(pt_multiplier=1.5, sl_multiplier=1.5, max_holding_bars=3))
        assert labeled.loc[0, "barrier_target"] == 0
        assert labeled.loc[0, "barrier_touch_type"] == "time_expiry"
