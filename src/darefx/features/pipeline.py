"""Feature and Labeling pipeline orchestrator for DareFX.

Combines:
1. Historical daily OHLCV bars from Parquet storage
2. Technical feature computation
3. Triple Barrier labeling
4. Exporting ML-ready training datasets
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from darefx.data.storage import ParquetStorage
from darefx.features.labels import TripleBarrierConfig, apply_triple_barrier
from darefx.features.technical import extract_features

logger = logging.getLogger(__name__)

EXCLUDE_FROM_FEATURES = {
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "tick_count",
    "barrier_target",
    "barrier_touch_idx",
    "barrier_ret",
    "barrier_touch_type",
}


def build_feature_dataset(
    symbol: str = "EURUSD",
    data_dir: Path | str = "data/processed",
    config: TripleBarrierConfig = TripleBarrierConfig(),
    save_output: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    """Build a complete, stationary feature and label dataset ready for machine learning.

    Parameters:
        symbol: Ticker symbol (e.g. 'EURUSD')
        data_dir: Location of processed annual Parquet files
        config: TripleBarrierConfig specifying barrier multipliers and holding window
        save_output: If True, writes eurusd_features.parquet to data_dir

    Returns:
        tuple of (dataset_df, feature_names_list)
    """
    storage = ParquetStorage(base_dir=data_dir)
    df_bars = storage.load_daily_bars(symbol=symbol)

    if df_bars.empty:
        raise ValueError(f"No daily bars found for {symbol} in {data_dir}. Run 'darefx fetch' first.")

    logger.info("Computing technical features for %d bars...", len(df_bars))
    df_features = extract_features(df_bars, dropna=True)

    logger.info("Applying Triple Barrier labeling (PT=%.1fx, SL=%.1fx, Window=%d)...",
                config.pt_multiplier, config.sl_multiplier, config.max_holding_bars)
    df_dataset = apply_triple_barrier(df_features, config=config)

    feature_cols = [c for c in df_dataset.columns if c not in EXCLUDE_FROM_FEATURES]

    logger.info("Dataset constructed: %d rows x %d features. Target distribution: %s",
                len(df_dataset), len(feature_cols), dict(df_dataset["barrier_target"].value_counts()))

    if save_output:
        out_path = Path(data_dir) / f"{symbol.lower()}_features.parquet"
        df_dataset.to_parquet(out_path, compression="snappy", index=False)
        logger.info("Saved ML-ready feature dataset to %s", out_path)

    return df_dataset, feature_cols
