"""Tests for WebSocket real-time market data streamer."""

import json
import time
from datetime import UTC, datetime

from darefx.data.ws_streamer import RealtimeBar, WebSocketStreamer


def test_realtime_bar_properties():
    bullish = RealtimeBar(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        open_price=65000.0,
        high_price=65500.0,
        low_price=64900.0,
        close_price=65200.0,
        volume=12.5,
    )
    assert bullish.is_bullish is True

    bearish = RealtimeBar(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        open_price=65000.0,
        high_price=65500.0,
        low_price=64000.0,
        close_price=64200.0,
        volume=15.0,
    )
    assert bearish.is_bullish is False


def test_parse_binance_message():
    streamer = WebSocketStreamer()
    raw_payload = json.dumps({
        "e": "kline",
        "E": 1672531200000,
        "s": "BTCUSDT",
        "k": {
            "t": 1672531200000,
            "T": 1672531259999,
            "s": "BTCUSDT",
            "i": "1m",
            "f": 100,
            "L": 200,
            "o": "16500.00",
            "c": "16550.00",
            "h": "16580.00",
            "l": "16490.00",
            "v": "24.5",
            "n": 100,
            "x": False,
            "q": "405000.00",
            "V": "12.0",
            "Q": "198000.00",
            "B": "0",
        },
    })

    bar = streamer.parse_binance_message(raw_payload)
    assert bar is not None
    assert bar.symbol == "BTCUSDT"
    assert bar.open_price == 16500.0
    assert bar.close_price == 16550.0
    assert bar.high_price == 16580.0
    assert bar.low_price == 16490.0
    assert bar.volume == 24.5
    assert bar.is_closed is False


def test_parse_alpaca_message():
    streamer = WebSocketStreamer()
    raw_payload = json.dumps([
        {
            "T": "b",
            "S": "AAPL",
            "o": 180.25,
            "h": 181.00,
            "l": 179.90,
            "c": 180.80,
            "v": 15400,
            "t": "2026-11-05T14:30:00Z",
            "n": 520,
            "vw": 180.55,
        }
    ])

    bar = streamer.parse_alpaca_message(raw_payload)
    assert bar is not None
    assert bar.symbol == "AAPL"
    assert bar.open_price == 180.25
    assert bar.close_price == 180.80
    assert bar.volume == 15400.0
    assert bar.is_closed is True


def test_streamer_fallback_simulator_lifecycle():
    received_bars = []

    def on_bar(b: RealtimeBar):
        received_bars.append(b)

    streamer = WebSocketStreamer(on_bar_callback=on_bar)
    streamer.start(symbol="EURUSD", interval="1m")

    # Wait briefly for simulated ticks
    time.sleep(2.2)
    streamer.stop()

    assert len(received_bars) >= 1
    first_bar = received_bars[0]
    assert first_bar.symbol == "EURUSD"
    assert first_bar.open_price > 0.0
