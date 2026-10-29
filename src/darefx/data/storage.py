"""Parquet storage manager for DareFX historical data.

Provides:
- Annual partitioning (e.g. data/processed/eurusd_daily_2024.parquet)
- PyArrow schema enforcement with microsecond UTC timestamps
- Snappy compression for fast I/O and minimal disk footprint
- Sub-second time-range queries across decades of data
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

OHLCV_ARROW_SCHEMA = pa.schema(
    [
        ("timestamp", pa.timestamp("us", tz="UTC")),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
        ("tick_count", pa.int64()),
    ]
)


class ParquetStorage:
    """Manages reading and writing OHLCV datasets in Parquet format."""

    def __init__(self, base_dir: Path | str = "data/processed") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_daily_bars(
        self,
        df_bars: pd.DataFrame,
        symbol: str = "EURUSD",
        partition_by_year: bool = True,
    ) -> list[Path]:
        """Save a daily OHLCV DataFrame into Parquet files.

        Parameters:
            df_bars: DataFrame conforming to OHLCV schema
            symbol: Ticker symbol (e.g. 'EURUSD')
            partition_by_year: If True, writes separate files per year

        Returns:
            List of Paths to the saved Parquet files
        """
        if df_bars.empty:
            logger.warning("Empty DataFrame passed to save_daily_bars; nothing saved.")
            return []

        df = df_bars.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp")
        df = df.drop_duplicates(subset=["timestamp"], keep="last")

        if not partition_by_year:
            file_path = self.base_dir / f"{symbol.lower()}_daily_all.parquet"
            table = pa.Table.from_pandas(df, schema=OHLCV_ARROW_SCHEMA, preserve_index=False)
            pq.write_table(table, file_path, compression="snappy")
            return [file_path]

        saved_files: list[Path] = []
        df["_year"] = df["timestamp"].dt.year

        for year, group in df.groupby("_year"):
            year_df = group.drop(columns=["_year"]).copy()
            file_path = self.base_dir / f"{symbol.lower()}_daily_{year}.parquet"

            # Merge with existing file if present to support incremental updates
            if file_path.exists():
                existing_table = pq.read_table(file_path)
                existing_df = existing_table.to_pandas()
                merged = pd.concat([existing_df, year_df], ignore_index=True)
                merged = merged.drop_duplicates(subset=["timestamp"], keep="last")
                merged = merged.sort_values("timestamp")
                year_df = merged

            table = pa.Table.from_pandas(year_df, schema=OHLCV_ARROW_SCHEMA, preserve_index=False)
            pq.write_table(table, file_path, compression="snappy")
            saved_files.append(file_path)

        return saved_files

    def load_daily_bars(
        self,
        symbol: str = "EURUSD",
        start_date: str | pd.Timestamp | None = None,
        end_date: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Load daily bars for a given symbol across all partition files with optional date filtering."""
        pattern = f"{symbol.lower()}_daily_*.parquet"
        files = sorted(self.base_dir.glob(pattern))

        if not files:
            logger.info("No Parquet files found matching %s in %s", pattern, self.base_dir)
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "tick_count"])

        tables = [pq.read_table(f) for f in files]
        combined_table = pa.concat_tables(tables)
        df = combined_table.to_pandas()
        df = df.sort_values("timestamp")
        df = df.drop_duplicates(subset=["timestamp"], keep="last")
        df = df.reset_index(drop=True)

        if start_date is not None:
            ts_start = pd.to_datetime(start_date, utc=True)
            df = df[df["timestamp"] >= ts_start]

        if end_date is not None:
            ts_end = pd.to_datetime(end_date, utc=True)
            df = df[df["timestamp"] <= ts_end]

        return df.reset_index(drop=True)
