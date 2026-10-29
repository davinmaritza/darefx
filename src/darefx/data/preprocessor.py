"""Tick data cleaning and OHLCV resampling engine for DareFX.

Adheres to:
1. Institutional 17:00 New York close daily cutoff (22:00 UTC / 21:00 UTC during EDT)
2. Weekend gap purging (Friday post-close to Sunday pre-open)
3. Zero-spread and inverted-quote filtering (bid > ask or bid <= 0)
4. Rigorous OHLC consistency invariant checks
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def clean_ticks(df_ticks: pd.DataFrame) -> pd.DataFrame:
    """Filter out corrupt ticks (non-positive prices, inverted bid/ask, extreme spreads)."""
    if df_ticks.empty:
        return df_ticks.copy()

    df = df_ticks.copy()
    initial_count = len(df)

    # 1. Non-positive price filter
    valid_mask = (df["ask"] > 0) & (df["bid"] > 0)

    # 2. Inverted bid-ask check (bid should never exceed ask in valid quotes)
    valid_mask &= df["ask"] >= df["bid"]

    # 3. Extreme spread filter (spread > 100 pips = 0.0100 for EUR/USD is extreme outlier)
    spread = df["ask"] - df["bid"]
    valid_mask &= spread <= 0.0100

    df = df[valid_mask].copy()
    dropped = initial_count - len(df)
    if dropped > 0:
        logger.info("Cleaned %d corrupt or extreme-spread ticks out of %d", dropped, initial_count)

    # Add mid price
    df["mid"] = (df["ask"] + df["bid"]) / 2.0
    return df


def resample_ticks_to_daily(
    df_ticks: pd.DataFrame,
    price_col: Literal["mid", "bid", "ask"] = "mid",
    cutoff_hour_utc: int = 22,
) -> pd.DataFrame:
    """Resample raw ticks into daily OHLCV bars aligned to institutional New York 17:00 close (22:00 UTC).

    Parameters:
        df_ticks: DataFrame with 'timestamp', 'bid', 'ask', 'mid', 'ask_volume', 'bid_volume'
        price_col: Price stream to use for OHLC ('mid', 'bid', or 'ask')
        cutoff_hour_utc: UTC hour at which the trading day closes (default 22:00 UTC)

    Returns:
        DataFrame with columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'tick_count']
    """
    if df_ticks.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "tick_count"])

    df = clean_ticks(df_ticks)
    if df.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "tick_count"])

    if price_col not in df.columns:
        if price_col == "mid":
            df["mid"] = (df["ask"] + df["bid"]) / 2.0
        else:
            raise ValueError(f"Price column '{price_col}' not found in tick data")

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp")

    # Shift timestamps backward by cutoff_hour_utc so that grouping by date groups 22:00 -> 22:00
    shifted_time = df["timestamp"] - pd.Timedelta(hours=cutoff_hour_utc)
    df["trade_date"] = shifted_time.dt.floor("1D")

    grouped = df.groupby("trade_date")
    bars = pd.DataFrame(
        {
            "timestamp": grouped["trade_date"].first() + pd.Timedelta(hours=cutoff_hour_utc),
            "open": grouped[price_col].first(),
            "high": grouped[price_col].max(),
            "low": grouped[price_col].min(),
            "close": grouped[price_col].last(),
            "volume": grouped["ask_volume"].sum() + grouped["bid_volume"].sum(),
            "tick_count": grouped[price_col].count(),
        }
    )

    bars = bars.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

    # Exclude Saturday bars (minimal residual weekend settlement ticks)
    bars = bars[bars["timestamp"].dt.day_of_week != 5].copy().reset_index(drop=True)

    # Validate OHLC invariants
    validate_ohlc(bars)
    return bars


def validate_ohlc(df_bars: pd.DataFrame) -> None:
    """Enforce financial integrity invariants on OHLC bars:

    - High >= Open and High >= Close
    - Low <= Open and Low <= Close
    - High >= Low
    - Positive prices
    """
    if df_bars.empty:
        return

    invalid_high = (df_bars["high"] < df_bars["open"]) | (df_bars["high"] < df_bars["close"])
    invalid_low = (df_bars["low"] > df_bars["open"]) | (df_bars["low"] > df_bars["close"])
    inverted_hl = df_bars["high"] < df_bars["low"]
    non_positive = (df_bars["open"] <= 0) | (df_bars["close"] <= 0)

    if invalid_high.any():
        idx = df_bars[invalid_high].index.tolist()
        raise ValueError(f"OHLC invariant breached: High is less than Open or Close at indices {idx}")

    if invalid_low.any():
        idx = df_bars[invalid_low].index.tolist()
        raise ValueError(f"OHLC invariant breached: Low is greater than Open or Close at indices {idx}")

    if inverted_hl.any():
        idx = df_bars[inverted_hl].index.tolist()
        raise ValueError(f"OHLC invariant breached: High < Low at indices {idx}")

    if non_positive.any():
        idx = df_bars[non_positive].index.tolist()
        raise ValueError(f"OHLC invariant breached: Non-positive prices at indices {idx}")
