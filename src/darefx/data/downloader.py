"""Historical forex data downloader for DareFX.

Supports multiple data sources with automated fallback:
1. Yahoo Finance API (direct, unblocked, 20+ years of daily D1 bars)
2. Dukascopy tick data (.bi5 LZMA compressed binary stream)
3. Fallback and synthesis routines for offline development
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import lzma
from pathlib import Path
import struct
from typing import ClassVar
import urllib.request

import pandas as pd
import requests

from darefx.data.preprocessor import validate_ohlc

logger = logging.getLogger(__name__)

# Dukascopy constants
DUKASCOPY_BASE_URL = "https://datafeed.dukascopy.com/datafeed"
TICK_STRUCT_FORMAT = ">3I2f"
TICK_STRUCT_SIZE = struct.calcsize(TICK_STRUCT_FORMAT)


@dataclass(frozen=True)
class YahooFinanceDownloader:
    """Downloader for daily forex OHLCV bars from Yahoo Finance.

    Provides unblocked, low-latency access to 20+ years of EUR/USD data.
    """

    symbol: str = "EURUSD=X"
    timeout_sec: int = 15

    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }

    def fetch_daily_bars(self, range_str: str = "25y") -> pd.DataFrame:
        """Download daily bars directly from Yahoo Finance API.

        Parameters:
            range_str: Historical range string, e.g. '1y', '5y', '10y', '25y', or 'max'

        Returns:
            DataFrame with columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'tick_count']
        """
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{self.symbol}?range={range_str}&interval=1d"
        req = urllib.request.Request(url, headers=self.HEADERS)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                payload = json.loads(response.read().decode())
        except Exception as err:
            logger.error("Failed to fetch from Yahoo Finance: %s", err)
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "tick_count"])

        try:
            result = payload["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]

            opens = quote.get("open", [])
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            closes = quote.get("close", [])
            volumes = quote.get("volume", [0] * len(timestamps))

            dts = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts in timestamps]

            df = pd.DataFrame(
                {
                    "timestamp": dts,
                    "open": opens,
                    "high": highs,
                    "low": lows,
                    "close": closes,
                    "volume": [float(v) if v is not None else 0.0 for v in volumes],
                    "tick_count": [1000] * len(timestamps),  # Representative tick count proxy
                }
            )

            # Drop missing values (market holidays or incomplete quotes)
            df = df.dropna(subset=["open", "high", "low", "close"])

            # Filter weekend records if present
            df = df[df["timestamp"].dt.day_of_week < 5].copy()

            # Fix any micro-inconsistencies where high < max(open, close) due to provider rounding
            df["high"] = df[["high", "open", "close"]].max(axis=1)
            df["low"] = df[["low", "open", "close"]].min(axis=1)

            df = df.sort_values("timestamp").reset_index(drop=True)

            validate_ohlc(df)
            return df
        except (KeyError, IndexError, ValueError) as err:
            logger.error("Error parsing Yahoo Finance response: %s", err)
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "tick_count"])


@dataclass(frozen=True)
class DukascopyDownloader:
    """Downloader and unpacker for Dukascopy bi5 tick data."""

    symbol: str = "EURUSD"
    point_divider: float = 100_000.0
    timeout_sec: int = 15
    cache_dir: Path | None = None
    max_retries: int = 3

    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": "Mozilla/5.0 (X-UA-Compatible; DareFX-Quant/1.0)",
        "Accept": "*/*",
    }

    def get_hour_url(self, dt: datetime) -> str:
        """Construct the Dukascopy URL for a specific UTC hour."""
        utc_dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        year = utc_dt.year
        month_0indexed = utc_dt.month - 1
        day = utc_dt.day
        hour = utc_dt.hour
        return (
            f"{DUKASCOPY_BASE_URL}/{self.symbol}/"
            f"{year:04d}/{month_0indexed:02d}/{day:02d}/{hour:02d}h_ticks.bi5"
        )

    def download_hour_bytes(self, dt: datetime) -> bytes:
        """Download raw compressed bi5 bytes for a given UTC hour with retries."""
        url = self.get_hour_url(dt)

        if self.cache_dir:
            cache_file = self.cache_dir / f"{self.symbol}_{dt.strftime('%Y%m%d_%H')}h.bi5"
            if cache_file.exists():
                return cache_file.read_bytes()

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(url, headers=self.HEADERS, timeout=self.timeout_sec)
                # Check for Internet Positif or ISP blocking intercept
                if "internet positif" in response.text.lower():
                    logger.warning("Dukascopy URL is blocked by ISP / Internet Positif.")
                    return b""
                if response.status_code == 200:
                    payload = response.content
                    if self.cache_dir and payload:
                        self.cache_dir.mkdir(parents=True, exist_ok=True)
                        cache_file = self.cache_dir / f"{self.symbol}_{dt.strftime('%Y%m%d_%H')}h.bi5"
                        cache_file.write_bytes(payload)
                    return payload
                if response.status_code == 404:
                    return b""
            except requests.RequestException as err:
                logger.warning("Request error for %s: %s (attempt %d/%d)", url, err, attempt, self.max_retries)

        return b""

    def unpack_bi5(self, compressed_bytes: bytes, base_hour: datetime) -> pd.DataFrame:
        """Decompress LZMA bi5 bytes and unpack into a structured tick DataFrame."""
        if not compressed_bytes:
            return pd.DataFrame(columns=["timestamp", "ask", "bid", "ask_volume", "bid_volume"])

        try:
            raw_bytes = lzma.decompress(compressed_bytes)
        except (lzma.LZMAError, Exception) as err:
            logger.error("LZMA decompress error: %s", err)
            return pd.DataFrame(columns=["timestamp", "ask", "bid", "ask_volume", "bid_volume"])

        total_records = len(raw_bytes) // TICK_STRUCT_SIZE
        if total_records == 0:
            return pd.DataFrame(columns=["timestamp", "ask", "bid", "ask_volume", "bid_volume"])

        base_utc = base_hour.astimezone(timezone.utc) if base_hour.tzinfo else base_hour.replace(tzinfo=timezone.utc)
        base_epoch_ms = int(base_utc.timestamp() * 1000)

        timestamps: list[datetime] = []
        asks: list[float] = []
        bids: list[float] = []
        ask_vols: list[float] = []
        bid_vols: list[float] = []

        for offset in range(0, total_records * TICK_STRUCT_SIZE, TICK_STRUCT_SIZE):
            chunk = raw_bytes[offset : offset + TICK_STRUCT_SIZE]
            time_ms, ask_int, bid_int, ask_vol, bid_vol = struct.unpack(TICK_STRUCT_FORMAT, chunk)

            tick_epoch_ms = base_epoch_ms + time_ms
            dt = datetime.fromtimestamp(tick_epoch_ms / 1000.0, tz=timezone.utc)

            timestamps.append(dt)
            asks.append(ask_int / self.point_divider)
            bids.append(bid_int / self.point_divider)
            ask_vols.append(float(ask_vol))
            bid_vols.append(float(bid_vol))

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "ask": asks,
                "bid": bids,
                "ask_volume": ask_vols,
                "bid_volume": bid_vols,
            }
        )
