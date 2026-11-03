import os
from datetime import datetime, timezone
import pytest
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
from darefx.gui.components.metric_card import MetricCard
from darefx.gui.components.positions_table import PositionsTableWidget
from darefx.gui.components.control_panel import ControlPanelWidget
from darefx.trading.mt5_bridge import Position

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_metric_card_update(qapp) -> None:
    card = MetricCard("Equity", "$94,320.50", "Floating: +$1,220.00", is_positive=True)
    assert card.title_label.text() == "EQUITY"
    assert card.value_label.text() == "$94,320.50"
    card.update_values("$95,000.00", "+$1,900.00", is_positive=True)
    assert card.value_label.text() == "$95,000.00"

def test_positions_table_rendering(qapp) -> None:
    table = PositionsTableWidget()
    test_positions = [
        Position(
            ticket=11191991916,
            symbol="EURUSD",
            order_type="SELL",
            volume=0.20,
            open_price=1.12450,
            current_price=1.11950,
            sl=1.12450,
            tp=1.11000,
            profit=100.0,
            open_time=datetime.now(timezone.utc),
        )
    ]
    table.update_positions(test_positions)
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "#11191991916"
