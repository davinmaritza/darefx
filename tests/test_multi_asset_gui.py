"""Unit tests for Multi-Asset GUI Cockpit components."""

import os
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from darefx.gui.components.crypto_panel import CryptoPanelWidget
from darefx.gui.components.screener_table import ScreenerTableWidget
from darefx.gui.components.stock_panel import StockPanelWidget
from darefx.gui.main_window import DareFXMainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_crypto_panel_widget_lifecycle(qapp) -> None:
    panel = CryptoPanelWidget()
    assert panel.card_balance is not None
    assert panel.table is not None
    assert panel.adapter.is_simulation

    # Trigger refresh
    panel.refresh_state()
    assert "USDT" in panel.card_balance.title_label.text()


def test_stock_panel_widget_lifecycle(qapp) -> None:
    panel = StockPanelWidget()
    assert panel.card_cash is not None
    assert panel.table is not None
    assert panel.adapter.is_simulation

    # Trigger refresh
    panel.refresh_state()
    assert "KAS" in panel.card_cash.title_label.text() or "SALDO" in panel.card_cash.title_label.text()


def test_screener_table_widget_lifecycle(qapp) -> None:
    screener = ScreenerTableWidget()
    assert screener.table is not None
    assert screener.filter_combo is not None
    assert screener.market_combo is not None

    # Run scan on Crypto
    screener.market_combo.setCurrentIndex(0)
    screener.run_scan()
    assert len(screener.candidates) > 0
    assert screener.table.rowCount() > 0

    # Run scan on Stocks
    screener.market_combo.setCurrentIndex(1)
    screener.run_scan()
    assert len(screener.candidates) > 0


def test_main_window_has_all_four_multi_asset_tabs(qapp) -> None:
    win = DareFXMainWindow(simulation=True)
    assert hasattr(win, "tabs")
    assert win.tabs.count() == 4
    assert "Forex" in win.tabs.tabText(0)
    assert "Crypto" in win.tabs.tabText(1)
    assert "Stocks" in win.tabs.tabText(2)
    assert "Screener" in win.tabs.tabText(3)
    win.close()
