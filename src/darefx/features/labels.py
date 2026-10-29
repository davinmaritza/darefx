"""Triple Barrier Labeling engine based on Marcos López de Prado.

References:
    López de Prado, M. (2018). Advances in Financial Machine Learning.
    Chapter 3: The Triple-Barrier Method.

Labels financial time-series observations based on which barrier price path touches first:
- Upper Barrier (+1): Profit-taking boundary (entry + width * volatility)
- Lower Barrier (-1): Stop-loss boundary (entry - width * volatility)
- Vertical Barrier (0): Maximum holding duration expiration
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TripleBarrierConfig:
    """Configuration parameters for the Triple Barrier labeling method."""

    pt_multiplier: float = 1.5  # Profit target barrier multiplier (e.g. 1.5 * ATR)
    sl_multiplier: float = 1.5  # Stop loss barrier multiplier (e.g. 1.5 * ATR)
    max_holding_bars: int = 5   # Vertical barrier: maximum holding duration in daily bars
    volatility_metric: str = "atr"  # 'atr' or 'std'


def apply_triple_barrier(
    df_bars: pd.DataFrame,
    config: TripleBarrierConfig = TripleBarrierConfig(),
) -> pd.DataFrame:
    """Compute Triple Barrier labels for every bar in the input dataset.

    Parameters:
        df_bars: DataFrame with ['timestamp', 'open', 'high', 'low', 'close'] and optionally 'atr_14'
        config: TripleBarrierConfig with barrier multipliers and holding window

    Returns:
        DataFrame with original columns plus:
        - 'barrier_target': +1 (Buy profit), -1 (Stop hit), 0 (Time expiry)
        - 'barrier_touch_idx': Index of the bar where barrier was touched
        - 'barrier_ret': Realized return at barrier touch
        - 'barrier_touch_type': 'profit_target', 'stop_loss', or 'time_expiry'
    """
    if df_bars.empty:
        return df_bars.copy()

    df = df_bars.copy().reset_index(drop=True)
    n = len(df)

    # Ensure volatility metric is available
    if "atr_14" in df.columns:
        volatility = df["atr_14"]
    else:
        # Fallback to rolling standard deviation of close over 14 bars
        volatility = df["close"].rolling(14).std().bfill()

    targets = np.zeros(n, dtype=int)
    touch_indices = np.zeros(n, dtype=int)
    realized_rets = np.zeros(n, dtype=float)
    touch_types = [""] * n

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    vols = volatility.values

    # Scan forward for each bar
    for i in range(n):
        entry_price = closes[i]
        vol = vols[i]

        if np.isnan(vol) or vol <= 0:
            vol = entry_price * 0.005  # Fallback 50 pips

        upper_barrier = entry_price + (config.pt_multiplier * vol)
        lower_barrier = entry_price - (config.sl_multiplier * vol)
        max_idx = min(i + config.max_holding_bars, n - 1)

        touched = False
        for j in range(i + 1, max_idx + 1):
            curr_high = highs[j]
            curr_low = lows[j]

            hit_upper = curr_high >= upper_barrier
            hit_lower = curr_low <= lower_barrier

            # If both hit in the same bar, assume conservative outcome (stop loss)
            if hit_upper and hit_lower:
                targets[i] = -1
                touch_indices[i] = j
                realized_rets[i] = (lower_barrier - entry_price) / entry_price
                touch_types[i] = "stop_loss"
                touched = True
                break
            elif hit_upper:
                targets[i] = 1
                touch_indices[i] = j
                realized_rets[i] = (upper_barrier - entry_price) / entry_price
                touch_types[i] = "profit_target"
                touched = True
                break
            elif hit_lower:
                targets[i] = -1
                touch_indices[i] = j
                realized_rets[i] = (lower_barrier - entry_price) / entry_price
                touch_types[i] = "stop_loss"
                touched = True
                break

        if not touched:
            # Vertical barrier reached (time expiration)
            exit_price = closes[max_idx]
            targets[i] = 0
            touch_indices[i] = max_idx
            realized_rets[i] = (exit_price - entry_price) / entry_price
            touch_types[i] = "time_expiry"

    df["barrier_target"] = targets
    df["barrier_touch_idx"] = touch_indices
    df["barrier_ret"] = realized_rets
    df["barrier_touch_type"] = touch_types

    return df
