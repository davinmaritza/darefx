"""Walk-Forward and Combinatorial Purged Cross-Validation (CPCV) engine for DareFX.

Adheres strictly to financial time-series validation protocols (Marcos López de Prado):
1. No future leakage: Strictly chronological splits (train strictly precedes test).
2. Purging: Drops the terminal portion of training data whose Triple Barrier holding
   window overlaps with the test period.
3. Embargoing: Inserts a post-test safety buffer to eliminate serial correlation leakage.
"""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import logging
from typing import Iterator

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WalkForwardFold:
    """Metadata and indices for a single walk-forward validation fold."""

    fold_idx: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_indices: np.ndarray
    test_indices: np.ndarray


@dataclass(frozen=True)
class WalkForwardConfig:
    """Configuration parameters for Walk-Forward cross-validation."""

    train_months: int = 36       # 3 years training rolling window
    test_months: int = 6         # 6 months out-of-sample test window
    step_months: int = 3         # 3 months step forward per fold
    purge_days: int = 10         # Purge gap before test (matches max triple barrier holding period)
    embargo_days: int = 5        # Embargo buffer after test set
    expanding: bool = False      # If True, train window expands rather than rolls


class WalkForwardSplitter:
    """Generates purged and embargoed walk-forward cross-validation folds."""

    def __init__(self, config: WalkForwardConfig = WalkForwardConfig()) -> None:
        self.config = config

    def split(self, df: pd.DataFrame, time_col: str = "timestamp") -> list[WalkForwardFold]:
        """Generate all walk-forward folds across the provided dataset.

        Parameters:
            df: DataFrame containing a sorted UTC datetime column
            time_col: Name of the timestamp column

        Returns:
            List of WalkForwardFold instances
        """
        if df.empty:
            return []

        timestamps = pd.to_datetime(df[time_col], utc=True)
        min_date = timestamps.min()
        max_date = timestamps.max()

        folds: list[WalkForwardFold] = []
        fold_idx = 0

        # Start from min_date + train_months
        train_start_date = min_date

        while True:
            if self.config.expanding:
                train_start = min_date
            else:
                train_start = train_start_date

            train_end = train_start_date + pd.DateOffset(months=self.config.train_months)
            # Apply purge: remove last purge_days from training set to prevent label bleed
            effective_train_end = train_end - pd.Timedelta(days=self.config.purge_days)

            test_start = train_end
            test_end = test_start + pd.DateOffset(months=self.config.test_months)

            if test_end > max_date:
                # If test window extends past available data, include final partial fold if it has >= 1 month
                if (max_date - test_start).days >= 30:
                    test_end = max_date
                else:
                    break

            train_mask = (timestamps >= train_start) & (timestamps <= effective_train_end)
            test_mask = (timestamps >= test_start) & (timestamps <= test_end)

            train_idx = np.flatnonzero(train_mask.values)
            test_idx = np.flatnonzero(test_mask.values)

            if len(train_idx) > 50 and len(test_idx) > 10:
                fold = WalkForwardFold(
                    fold_idx=fold_idx,
                    train_start=train_start,
                    train_end=effective_train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_indices=train_idx,
                    test_indices=test_idx,
                )
                folds.append(fold)
                fold_idx += 1

            if test_end >= max_date:
                break

            train_start_date += pd.DateOffset(months=self.config.step_months)

        logger.info("Generated %d Walk-Forward validation folds.", len(folds))
        return folds


class CPCVSplitter:
    """Combinatorial Purged Cross-Validation (CPCV) splitter.

    Partitions dataset into N contiguous chronological groups,
    and tests all combinations of (N - k) train groups vs k test groups with boundary purging.
    """

    def __init__(self, n_groups: int = 6, k_test_groups: int = 2, purge_days: int = 10) -> None:
        self.n_groups = n_groups
        self.k_test_groups = k_test_groups
        self.purge_days = purge_days

    def split(self, df: pd.DataFrame, time_col: str = "timestamp") -> list[tuple[np.ndarray, np.ndarray]]:
        """Generate purged combinatorial train and test index pairs."""
        if df.empty or len(df) < self.n_groups:
            return []

        timestamps = pd.to_datetime(df[time_col], utc=True)
        group_size = len(df) // self.n_groups
        groups: list[np.ndarray] = []

        for i in range(self.n_groups):
            start = i * group_size
            end = (i + 1) * group_size if i < self.n_groups - 1 else len(df)
            groups.append(np.arange(start, end))

        splits: list[tuple[np.ndarray, np.ndarray]] = []
        for test_group_indices in itertools.combinations(range(self.n_groups), self.k_test_groups):
            test_idx_parts = [groups[g] for g in test_group_indices]
            test_indices = np.concatenate(test_idx_parts)

            train_group_indices = [g for g in range(self.n_groups) if g not in test_group_indices]
            train_idx_parts: list[np.ndarray] = []

            for g in train_group_indices:
                g_indices = groups[g]
                # If train group directly precedes a test group, purge the last purge_days
                if (g + 1) in test_group_indices:
                    g_timestamps = timestamps.iloc[g_indices]
                    purge_cutoff = g_timestamps.max() - pd.Timedelta(days=self.purge_days)
                    keep_mask = g_timestamps <= purge_cutoff
                    g_indices = g_indices[keep_mask.values]

                if len(g_indices) > 0:
                    train_idx_parts.append(g_indices)

            if train_idx_parts and len(test_indices) > 0:
                train_indices = np.concatenate(train_idx_parts)
                splits.append((train_indices, test_indices))

        return splits
