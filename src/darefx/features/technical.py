"""Feature engineering module for DareFX.

Computes stationary and normalized technical indicators on daily OHLCV bars:
- Momentum: RSI(14), MACD(12,26,9), Stochastic(14,3)
- Volatility: ATR(14), Normalized ATR (NATR), Bollinger Bands(20,2), BB %B, BB Width
- Trend: ADX(14), +DI, -DI, EMAs (9, 21, 50, 200), EMA distance ratios
- Returns & Memory: Log returns (1d, 5d, 21d), rolling volatility
- Scaling: Backward-looking rolling z-score normalization (strictly zero look-ahead bias)
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Moving Average Convergence Divergence."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist


def compute_bollinger_bands(
    series: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands, Band Width, and %B."""
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)

    # %B: (price - lower) / (upper - lower)
    bandwidth = upper - lower
    pct_b = (series - lower) / bandwidth.replace(0.0, np.nan)
    band_width_pct = bandwidth / middle.replace(0.0, np.nan)

    return upper, middle, lower, pct_b, band_width_pct


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> tuple[pd.Series, pd.Series]:
    """Average True Range (ATR) and Normalized ATR (NATR in %)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    natr = (atr / close) * 100.0
    return atr, natr


def compute_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """Stochastic Oscillator (%K and %D)."""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    denom = highest_high - lowest_low
    fast_k = 100.0 * ((close - lowest_low) / denom.replace(0.0, np.nan))
    slow_k = fast_k.rolling(window=d_period).mean()
    slow_d = slow_k.rolling(window=d_period).mean()
    return slow_k, slow_d


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Average Directional Index (ADX, +DI, -DI)."""
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    tr_smoothed = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    plus_dm_smoothed = pd.Series(plus_dm, index=high.index).ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    minus_dm_smoothed = pd.Series(minus_dm, index=high.index).ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    plus_di = 100.0 * (plus_dm_smoothed / tr_smoothed.replace(0.0, np.nan))
    minus_di = 100.0 * (minus_dm_smoothed / tr_smoothed.replace(0.0, np.nan))

    dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan))
    adx = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return adx, plus_di, minus_di


def rolling_zscore(series: pd.Series, window: int = 60) -> pd.Series:
    """Rolling backward-looking z-score normalization (prevents look-ahead bias)."""
    mean = series.rolling(window=window, min_periods=max(5, window // 4)).mean()
    std = series.rolling(window=window, min_periods=max(5, window // 4)).std()
    return (series - mean) / std.replace(0.0, np.nan)


def extract_features(df_bars: pd.DataFrame, dropna: bool = True) -> pd.DataFrame:
    """Extract complete tabular feature set from raw daily OHLCV bars.

    Parameters:
        df_bars: DataFrame containing ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        dropna: If True, drops initial warm-up rows containing NaN from 200-period indicators

    Returns:
        DataFrame containing original prices plus all engineered features
    """
    if df_bars.empty:
        return df_bars.copy()

    df = df_bars.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    open_ = df["open"]

    # 1. Momentum Features
    df["rsi_14"] = compute_rsi(close, period=14)
    macd_line, macd_sig, macd_hist = compute_macd(close, fast=12, slow=26, signal=9)
    df["macd"] = macd_line
    df["macd_signal"] = macd_sig
    df["macd_hist"] = macd_hist
    stoch_k, stoch_d = compute_stochastic(high, low, close, k_period=14, d_period=3)
    df["stoch_k"] = stoch_k
    df["stoch_d"] = stoch_d

    # 2. Volatility Features
    atr, natr = compute_atr(high, low, close, period=14)
    df["atr_14"] = atr
    df["natr_14"] = natr
    bb_upper, bb_mid, bb_lower, bb_pct, bb_width = compute_bollinger_bands(close, period=20, num_std=2.0)
    df["bb_upper"] = bb_upper
    df["bb_middle"] = bb_mid
    df["bb_lower"] = bb_lower
    df["bb_pct"] = bb_pct
    df["bb_width"] = bb_width

    # 3. Trend Features
    adx, plus_di, minus_di = compute_adx(high, low, close, period=14)
    df["adx_14"] = adx
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    # Moving average distances (normalized as % difference from close)
    for span in [9, 21, 50, 200]:
        ema = close.ewm(span=span, adjust=False).mean()
        df[f"ema_{span}"] = ema
        df[f"ema_dist_{span}"] = (close - ema) / ema

    # 4. Returns & Multi-Horizon Momentum
    df["return_1d"] = np.log(close / close.shift(1))
    df["return_5d"] = np.log(close / close.shift(5))
    df["return_21d"] = np.log(close / close.shift(21))

    # Bar shape features
    bar_range = (high - low).replace(0.0, np.nan)
    df["body_pct"] = (close - open_).abs() / bar_range
    df["upper_shadow_pct"] = (high - np.maximum(open_, close)) / bar_range
    df["lower_shadow_pct"] = (np.minimum(open_, close) - low) / bar_range

    # 5. Calendar Features (Cyclical seasonality)
    ts = pd.to_datetime(df["timestamp"])
    df["day_of_week"] = ts.dt.day_of_week
    df["month"] = ts.dt.month

    # 6. Stationary Rolling Z-Scores for Key Oscillators
    df["zscore_rsi"] = rolling_zscore(df["rsi_14"], window=60)
    df["zscore_macd_hist"] = rolling_zscore(df["macd_hist"], window=60)
    df["zscore_natr"] = rolling_zscore(df["natr_14"], window=60)

    if dropna:
        # Drop initial 200 bars used to initialize EMA 200
        df = df.dropna().reset_index(drop=True)

    return df
