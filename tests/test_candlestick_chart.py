"""Unit tests for CandlestickChartWidget and CandlestickCanvas."""

import os
from datetime import UTC, datetime, timedelta

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from darefx.gui.components.candlestick_chart import (
    CandleBar,
    CandlestickCanvas,
    CandlestickChartWidget,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_bars() -> list[CandleBar]:
    now = datetime.now(UTC)
    bars: list[CandleBar] = []
    price = 100.0
    for i in range(40):
        dt = now + timedelta(days=i)
        bar_open = price
        bar_close = price + (1.0 if i % 2 == 0 else -0.8)
        bar_high = max(bar_open, bar_close) + 0.5
        bar_low = min(bar_open, bar_close) - 0.5
        bar_vol = 1000.0 + i * 10
        bars.append(
            CandleBar(
                timestamp=dt,
                open=bar_open,
                high=bar_high,
                low=bar_low,
                close=bar_close,
                volume=bar_vol,
                ema20=price,
                ema50=price,
            )
        )
        price = bar_close
    return bars



def test_candlestick_canvas_set_bars(qapp: QApplication, sample_bars: list[CandleBar]) -> None:
    canvas = CandlestickCanvas()
    canvas.resize(600, 400)
    canvas.set_bars(sample_bars)
    assert len(canvas.bars) == 40
    assert canvas.visible_count <= 40
    assert canvas.visible_start >= 0

    # Test reset view
    canvas.reset_view()
    assert canvas.visible_count == 40


def test_candlestick_canvas_toggles(qapp: QApplication, sample_bars: list[CandleBar]) -> None:
    canvas = CandlestickCanvas()
    canvas.set_bars(sample_bars)

    canvas.show_ema = False
    assert canvas.show_ema is False

    canvas.show_volume = False
    assert canvas.show_volume is False

    canvas.show_crosshair = False
    assert canvas.show_crosshair is False


def test_chart_widget_markets_and_symbols(qapp: QApplication) -> None:
    chart = CandlestickChartWidget()
    assert chart.market_combo.count() == 3

    # Switch to Crypto
    chart.market_combo.setCurrentIndex(1)
    assert "BTC/USDT" in [chart.symbol_combo.itemText(i) for i in range(chart.symbol_combo.count())]

    # Switch to Stocks
    chart.market_combo.setCurrentIndex(2)
    assert "NVDA" in [chart.symbol_combo.itemText(i) for i in range(chart.symbol_combo.count())]

    # Switch to Forex
    chart.market_combo.setCurrentIndex(0)
    assert "EURUSD" in [chart.symbol_combo.itemText(i) for i in range(chart.symbol_combo.count())]


def test_chart_widget_hud_update(qapp: QApplication, sample_bars: list[CandleBar]) -> None:
    chart = CandlestickChartWidget()
    chart.canvas.set_bars(sample_bars)
    chart._on_bar_hovered(sample_bars[-1])
    assert "O:" in chart.lbl_hud_data.text()
    assert "H:" in chart.lbl_hud_data.text()
    assert "L:" in chart.lbl_hud_data.text()
    assert "C:" in chart.lbl_hud_data.text()
