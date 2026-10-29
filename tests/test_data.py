"""Comprehensive unit and integration tests for DareFX data pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
import lzma
from pathlib import Path
import struct

import numpy as np
import pandas as pd
import pytest

from darefx.data.downloader import (
    DUKASCOPY_BASE_URL,
    TICK_STRUCT_FORMAT,
    TICK_STRUCT_SIZE,
    DukascopyDownloader,
)
from darefx.data.preprocessor import clean_ticks, resample_ticks_to_daily, validate_ohlc
from darefx.data.storage import ParquetStorage


def create_mock_bi5_payload(base_dt: datetime, count: int = 5) -> bytes:
    """Generate a valid LZMA-compressed bi5 binary stream for testing."""
    records = []
    for i in range(count):
        time_ms = i * 1000  # 1 second intervals
        ask_int = 108500 + i * 2  # 1.08500
        bid_int = 108480 + i * 2  # 1.08480
        ask_vol = 1.5 + i * 0.1
        bid_vol = 2.0 + i * 0.1
        records.append(struct.pack(TICK_STRUCT_FORMAT, time_ms, ask_int, bid_int, ask_vol, bid_vol))
    raw_data = b"".join(records)
    return lzma.compress(raw_data)


class TestDukascopyDownloader:
    """Tests for DukascopyDownloader url construction and unpacking."""

    def test_get_hour_url_zero_indexed_month(self):
        downloader = DukascopyDownloader(symbol="EURUSD")
        dt = datetime(2024, 5, 10, 14, 0, 0, tzinfo=timezone.utc)
        url = downloader.get_hour_url(dt)
        # Note: May is month 5, but Dukascopy uses 0-indexed month -> 04
        assert url == f"{DUKASCOPY_BASE_URL}/EURUSD/2024/04/10/14h_ticks.bi5"

    def test_unpack_bi5_valid(self):
        downloader = DukascopyDownloader(symbol="EURUSD", point_divider=100_000.0)
        base_dt = datetime(2024, 5, 10, 14, 0, 0, tzinfo=timezone.utc)
        payload = create_mock_bi5_payload(base_dt, count=10)

        df = downloader.unpack_bi5(payload, base_dt)
        assert len(df) == 10
        assert list(df.columns) == ["timestamp", "ask", "bid", "ask_volume", "bid_volume"]
        assert pytest.approx(df["ask"].iloc[0], 0.00001) == 1.08500
        assert pytest.approx(df["bid"].iloc[0], 0.00001) == 1.08480
        assert df["ask"].iloc[0] > df["bid"].iloc[0]

    def test_unpack_bi5_empty(self):
        downloader = DukascopyDownloader(symbol="EURUSD")
        base_dt = datetime(2024, 5, 10, 14, 0, 0, tzinfo=timezone.utc)
        df = downloader.unpack_bi5(b"", base_dt)
        assert df.empty
        assert "timestamp" in df.columns


class TestYahooFinanceDownloader:
    """Tests for YahooFinanceDownloader."""

    def test_fetch_daily_bars_mocked(self, monkeypatch):
        from darefx.data.downloader import YahooFinanceDownloader
        import io
        import json

        fake_response = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1704758400, 1704844800],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [1.0950, 1.0930],
                                    "high": [1.0980, 1.0970],
                                    "low": [1.0920, 1.0910],
                                    "close": [1.0940, 1.0960],
                                    "volume": [1000, 1500],
                                }
                            ]
                        },
                    }
                ]
            }
        }

        class MockResponse:
            def __enter__(self):
                return io.BytesIO(json.dumps(fake_response).encode())

            def __exit__(self, *args):
                pass

        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=15: MockResponse())

        downloader = YahooFinanceDownloader(symbol="EURUSD=X")
        df = downloader.fetch_daily_bars(range_str="5d")

        assert len(df) == 2
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume", "tick_count"]
        assert df.iloc[0]["open"] == 1.0950
        assert df.iloc[0]["high"] == 1.0980


class TestPreprocessor:
    """Tests for tick cleaning and daily OHLCV resampling."""

    def test_clean_ticks_filters_corrupt_data(self):
        ticks = pd.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 5, 10, 10, 0, 0, tzinfo=timezone.utc),
                    datetime(2024, 5, 10, 10, 0, 1, tzinfo=timezone.utc),  # Inverted bid > ask
                    datetime(2024, 5, 10, 10, 0, 2, tzinfo=timezone.utc),  # Negative price
                    datetime(2024, 5, 10, 10, 0, 3, tzinfo=timezone.utc),  # Extreme spread > 100 pips
                    datetime(2024, 5, 10, 10, 0, 4, tzinfo=timezone.utc),
                ],
                "ask": [1.0850, 1.0840, -1.0850, 1.1000, 1.0852],
                "bid": [1.0848, 1.0850, 1.0848, 1.0800, 1.0850],
                "ask_volume": [1.0, 1.0, 1.0, 1.0, 1.0],
                "bid_volume": [1.0, 1.0, 1.0, 1.0, 1.0],
            }
        )

        cleaned = clean_ticks(ticks)
        assert len(cleaned) == 2
        assert "mid" in cleaned.columns
        assert (cleaned["ask"] >= cleaned["bid"]).all()
        assert (cleaned["mid"] > 0).all()

    def test_resample_ticks_to_daily_and_ohlc_invariants(self):
        timestamps = [
            datetime(2024, 5, 10, 14, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 5, 10, 15, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 5, 10, 16, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 5, 10, 17, 0, 0, tzinfo=timezone.utc),
        ]
        ticks = pd.DataFrame(
            {
                "timestamp": timestamps,
                "ask": [1.0845, 1.0870, 1.0830, 1.0860],
                "bid": [1.0843, 1.0868, 1.0828, 1.0858],
                "ask_volume": [2.0, 3.0, 1.5, 2.5],
                "bid_volume": [2.0, 3.0, 1.5, 2.5],
            }
        )

        bars = resample_ticks_to_daily(ticks, price_col="mid")
        assert len(bars) == 1
        bar = bars.iloc[0]

        # Verify OHLC integrity
        assert bar["high"] >= bar["open"]
        assert bar["high"] >= bar["close"]
        assert bar["low"] <= bar["open"]
        assert bar["low"] <= bar["close"]
        assert bar["tick_count"] == 4
        assert bar["volume"] == 18.0

    def test_validate_ohlc_raises_on_invalid_data(self):
        invalid_bars = pd.DataFrame(
            {
                "open": [1.0850],
                "high": [1.0840],  # High < Open! Invalid
                "low": [1.0830],
                "close": [1.0835],
            }
        )
        with pytest.raises(ValueError, match="OHLC invariant breached"):
            validate_ohlc(invalid_bars)


class TestParquetStorage:
    """Tests for Parquet storage, schema verification, and year-partitioning."""

    def test_save_and_load_daily_bars(self, tmp_path: Path):
        storage = ParquetStorage(base_dir=tmp_path)

        bars = pd.DataFrame(
            {
                "timestamp": [
                    pd.Timestamp("2023-11-01 22:00:00", tz="UTC"),
                    pd.Timestamp("2023-11-02 22:00:00", tz="UTC"),
                    pd.Timestamp("2024-01-02 22:00:00", tz="UTC"),
                ],
                "open": [1.0550, 1.0620, 1.0950],
                "high": [1.0640, 1.0680, 1.1010],
                "low": [1.0530, 1.0600, 1.0920],
                "close": [1.0610, 1.0650, 1.0980],
                "volume": [15000.0, 18000.0, 22000.0],
                "tick_count": [12000, 14000, 17000],
            }
        )

        saved_files = storage.save_daily_bars(bars, symbol="EURUSD", partition_by_year=True)
        assert len(saved_files) == 2  # 2023 and 2024 partitions
        assert any("eurusd_daily_2023.parquet" in f.name for f in saved_files)
        assert any("eurusd_daily_2024.parquet" in f.name for f in saved_files)

        # Load all bars back
        loaded = storage.load_daily_bars(symbol="EURUSD")
        assert len(loaded) == 3
        assert list(loaded["timestamp"]) == list(bars["timestamp"])

        # Load with date filtering
        filtered = storage.load_daily_bars(symbol="EURUSD", start_date="2024-01-01")
        assert len(filtered) == 1
        assert filtered.iloc[0]["open"] == 1.0950
