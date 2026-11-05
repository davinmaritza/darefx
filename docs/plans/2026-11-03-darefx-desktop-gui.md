# DareFX Desktop GUI Application Implementation Plan

**Goal:** Build a native desktop GUI application for DareFX using PySide6 with real-time MT5 position management, market diagnosis, background engine worker, system tray integration, and settings configuration dialog.

**Architecture:** Unified desktop application where the UI runs on Qt's main thread and the trading engine executes in a dedicated `QThread` (`TradingEngineWorker`). Communication between the UI and engine uses Qt Signals and Slots, preventing UI lockups. The application integrates with the Windows System Tray for background operation and persists trading parameters directly into `.env`.

**Tech Stack:** Python 3.12, PySide6 (Qt 6), MetaTrader 5 Bridge, Pydantic, python-dotenv, pytest.

**Spec:** Described in the confirmed design contract: Clean Professional Minimalist (Light / Neutral Gray enterprise banking theme), Full Dashboard Terminal (Account cards, Active positions table with close/BE actions, Quick control toolbar with Autotrade toggle / Panic Close All / Manual trade, AI analysis panel, Live log stream, Settings modal), System Tray minimize support, and Desktop shortcut via `pythonw.exe`.

## Global Constraints

- Must run on Windows with MetaTrader 5 Python library, and gracefully fallback to simulation mode when run on Linux or when MT5 terminal is offline.
- PySide6 must run headless in CI environments using `QT_QPA_PLATFORM=offscreen`.
- Zero lazy placeholders (`TODO`, `...`, or partial snippets); every code block must be fully runnable.
- High-impact emergency actions ("Panic Close All") must require confirmation modal before execution.
- Config updates via GUI Settings dialog must validate data types and persist to `.env` without destroying existing comments or keys.

## Review Focus

- Unconnected MT5 Terminal state: GUI must display "DISCONNECTED / SIMULATION" without crashing or locking UI thread.
- Zero positions state: Positions table must display an empty state placeholder ("Tidak ada posisi aktif") cleanly.
- Rapid button spamming: Action buttons ("Panic Close All", "Run Analysis") must be debounce-locked while an asynchronous request is in flight.
- Window close event: Closing the window must minimize to the Windows system tray with a notification tooltip rather than terminating active trades, unless user explicitly chooses "Exit" from the tray menu.
- Invalid input validation in Settings: Entering invalid float/numeric parameters (e.g. negative risk %, invalid lot) must show inline validation errors without corrupting `.env`.

---

### Task 1: Environment & Dependency Setup (`pyproject.toml`)

**Files:**
- Modify: `pyproject.toml:50-60`
- Test: `tests/test_gui_env.py`

**Interfaces:**
- Consumes: Python 3.12 environment
- Produces: `PySide6` package installed and importable in `.venv`

- [ ] **Step 1: Write failing test for PySide6 import**

Create `tests/test_gui_env.py`:
```python
def test_pyside6_is_available() -> None:
    import PySide6.QtCore
    import PySide6.QtWidgets
    assert PySide6.__version__ is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_gui_env.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'PySide6'`

- [ ] **Step 3: Update `pyproject.toml` and install PySide6**

Update `pyproject.toml` to add `gui = ["PySide6>=6.7.0"]` under `[project.optional-dependencies]`:
```toml
[project.optional-dependencies]
gui = [
    "PySide6>=6.7.0",
]
mt5 = [
    # Windows-only, install when needed for live trading
    # "MetaTrader5>=5.0.4424",
]
dev = [
    "pytest>=8.3",
    "pytest-cov>=5.0",
    "ruff>=0.6",
]
```
Install PySide6 into local `.venv`:
Run: `.venv/bin/pip install "PySide6>=6.7.0"`

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_gui_env.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/test_gui_env.py
git commit -m "chore(gui): add PySide6 dependency and verification test"
```

---

### Task 2: Design System & Styling (`src/darefx/gui/styles.py`)

**Files:**
- Create: `src/darefx/gui/__init__.py`
- Create: `src/darefx/gui/styles.py`
- Test: `tests/test_gui_styles.py`

**Interfaces:**
- Consumes: None
- Produces: `ThemeColors` constants, `get_application_stylesheet() -> str`, `get_badge_style(variant: str) -> str`

- [ ] **Step 1: Write failing test for styling functions**

Create `tests/test_gui_styles.py`:
```python
from darefx.gui.styles import ThemeColors, get_application_stylesheet, get_badge_style

def test_theme_colors_exist() -> None:
    assert ThemeColors.BG_PRIMARY.startswith("#")
    assert ThemeColors.TEXT_PRIMARY.startswith("#")
    assert ThemeColors.ACCENT_SUCCESS.startswith("#")
    assert ThemeColors.ACCENT_DANGER.startswith("#")

def test_stylesheet_returns_valid_qss() -> None:
    qss = get_application_stylesheet()
    assert "QMainWindow" in qss
    assert "QPushButton" in qss
    assert "QTableWidget" in qss

def test_badge_style_generation() -> None:
    buy_badge = get_badge_style("buy")
    sell_badge = get_badge_style("sell")
    assert "background-color" in buy_badge
    assert "background-color" in sell_badge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_gui_styles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'darefx.gui'`

- [ ] **Step 3: Create package and write styling implementation**

Create `src/darefx/gui/__init__.py`:
```python
"""DareFX Native Desktop GUI Package."""
```

Create `src/darefx/gui/styles.py`:
```python
"""Clean Professional Minimalist (Light / Neutral Gray Enterprise Banking) Theme for DareFX."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeColors:
    # Neutral Grayscale
    BG_PRIMARY: str = "#F8FAFC"      # Slate 50 (clean light background)
    BG_SURFACE: str = "#FFFFFF"      # Pure white card/table background
    BG_SUBTLE: str = "#F1F5F9"       # Slate 100 for hovered rows / headers
    BORDER_LIGHT: str = "#E2E8F0"    # Slate 200 border
    BORDER_STRONG: str = "#CBD5E1"   # Slate 300 divider

    # Typography
    TEXT_PRIMARY: str = "#0F172A"    # Slate 900 (deep readable charcoal)
    TEXT_MUTED: str = "#64748B"      # Slate 500 (secondary label gray)
    TEXT_ON_DARK: str = "#FFFFFF"

    # Accents & Financial Indicators
    ACCENT_PRIMARY: str = "#0284C7"  # Sky 600 (enterprise blue)
    ACCENT_PRIMARY_HOVER: str = "#0369A1"
    ACCENT_SUCCESS: str = "#15803D"  # Green 700 (solid profit green)
    ACCENT_SUCCESS_BG: str = "#DCFCE7"
    ACCENT_DANGER: str = "#B91C1C"   # Red 700 (controlled loss red)
    ACCENT_DANGER_BG: str = "#FEE2E2"
    ACCENT_WARNING: str = "#B45309"  # Amber 700
    ACCENT_WARNING_BG: str = "#FEF3C7"


def get_application_stylesheet() -> str:
    """Return comprehensive enterprise banking QSS stylesheet."""
    return f"""
    QMainWindow, QWidget#CentralWidget {{
        background-color: {ThemeColors.BG_PRIMARY};
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
        color: {ThemeColors.TEXT_PRIMARY};
        font-size: 13px;
    }}

    QFrame.metricCard {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_LIGHT};
        border-radius: 8px;
        padding: 12px;
    }}

    QTableWidget {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_LIGHT};
        border-radius: 6px;
        gridline-color: {ThemeColors.BORDER_LIGHT};
        selection-background-color: {ThemeColors.BG_SUBTLE};
        selection-color: {ThemeColors.TEXT_PRIMARY};
    }}

    QHeaderView::section {{
        background-color: {ThemeColors.BG_SUBTLE};
        color: {ThemeColors.TEXT_MUTED};
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        border: none;
        border-bottom: 1px solid {ThemeColors.BORDER_STRONG};
        padding: 6px 8px;
    }}

    QPushButton {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_STRONG};
        border-radius: 6px;
        color: {ThemeColors.TEXT_PRIMARY};
        padding: 6px 14px;
        font-weight: 500;
        font-size: 12px;
    }}

    QPushButton:hover {{
        background-color: {ThemeColors.BG_SUBTLE};
    }}

    QPushButton.primaryBtn {{
        background-color: {ThemeColors.ACCENT_PRIMARY};
        border: 1px solid {ThemeColors.ACCENT_PRIMARY};
        color: {ThemeColors.TEXT_ON_DARK};
        font-weight: 600;
    }}

    QPushButton.primaryBtn:hover {{
        background-color: {ThemeColors.ACCENT_PRIMARY_HOVER};
    }}

    QPushButton.dangerBtn {{
        background-color: {ThemeColors.ACCENT_DANGER_BG};
        border: 1px solid #FCA5A5;
        color: {ThemeColors.ACCENT_DANGER};
        font-weight: 600;
    }}

    QPushButton.dangerBtn:hover {{
        background-color: #F87171;
        color: #FFFFFF;
    }}

    QPushButton.successBtn {{
        background-color: {ThemeColors.ACCENT_SUCCESS_BG};
        border: 1px solid #86EFAC;
        color: {ThemeColors.ACCENT_SUCCESS};
        font-weight: 600;
    }}

    QPushButton.successBtn:hover {{
        background-color: #4ADE80;
        color: #FFFFFF;
    }}

    QTextEdit#LogConsole {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_LIGHT};
        border-radius: 6px;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 11px;
        color: {ThemeColors.TEXT_PRIMARY};
    }}

    QLineEdit, QDoubleSpinBox, QComboBox {{
        background-color: {ThemeColors.BG_SURFACE};
        border: 1px solid {ThemeColors.BORDER_STRONG};
        border-radius: 6px;
        padding: 5px 8px;
        color: {ThemeColors.TEXT_PRIMARY};
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {ThemeColors.ACCENT_PRIMARY};
    }}
    """


def get_badge_style(variant: str) -> str:
    """Generate inline stylesheet for status badges."""
    variant = variant.lower()
    if variant in ("buy", "active", "profit", "success"):
        return f"background-color: {ThemeColors.ACCENT_SUCCESS_BG}; color: {ThemeColors.ACCENT_SUCCESS}; font-weight: bold; border-radius: 4px; padding: 2px 6px;"
    if variant in ("sell", "danger", "loss", "shutdown"):
        return f"background-color: {ThemeColors.ACCENT_DANGER_BG}; color: {ThemeColors.ACCENT_DANGER}; font-weight: bold; border-radius: 4px; padding: 2px 6px;"
    if variant in ("warning", "paused", "neutral"):
        return f"background-color: {ThemeColors.ACCENT_WARNING_BG}; color: {ThemeColors.ACCENT_WARNING}; font-weight: bold; border-radius: 4px; padding: 2px 6px;"
    return f"background-color: {ThemeColors.BG_SUBTLE}; color: {ThemeColors.TEXT_MUTED}; font-weight: bold; border-radius: 4px; padding: 2px 6px;"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_gui_styles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/darefx/gui/__init__.py src/darefx/gui/styles.py tests/test_gui_styles.py
git commit -m "feat(gui): implement enterprise banking theme and QSS styles"
```

---

### Task 3: Background Engine Worker (`src/darefx/gui/worker.py`)

**Files:**
- Create: `src/darefx/gui/worker.py`
- Test: `tests/test_gui_worker.py`

**Interfaces:**
- Consumes: `MT5Bridge`, `MarketAnalyzer`, `CircuitBreaker`, `Position`, `AccountInfo`
- Produces: `TradingEngineWorker(QObject)` with signals:
  - `account_updated(object)`
  - `positions_updated(list)`
  - `analysis_completed(object)`
  - `log_emitted(str, str)`
  - `status_message(str)`

- [ ] **Step 1: Write failing test for TradingEngineWorker**

Create `tests/test_gui_worker.py`:
```python
import os
import pytest
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication
from darefx.gui.worker import TradingEngineWorker

@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app

def test_worker_signals_and_initialization(qapp) -> None:
    worker = TradingEngineWorker(simulation=True)
    assert worker is not None
    assert hasattr(worker, "account_updated")
    assert hasattr(worker, "positions_updated")
    assert hasattr(worker, "analysis_completed")
    assert hasattr(worker, "log_emitted")

def test_worker_poll_cycle_emits_data(qapp) -> None:
    worker = TradingEngineWorker(simulation=True)
    results = {}

    worker.account_updated.connect(lambda acc: results.setdefault("acc", acc))
    worker.positions_updated.connect(lambda pos: results.setdefault("pos", pos))

    worker.poll_account_and_positions()
    assert "acc" in results
    assert "pos" in results
    assert results["acc"].balance >= 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_gui_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'darefx.gui.worker'`

- [ ] **Step 3: Write TradingEngineWorker implementation**

Create `src/darefx/gui/worker.py`:
```python
"""Background worker thread and controller for MT5 trading engine."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from darefx.analysis.market_analyzer import MarketAnalysisReport, MarketAnalyzer
from darefx.risk.circuit_breaker import CircuitBreaker
from darefx.trading.mt5_bridge import AccountInfo, MT5Bridge, Position

logger = logging.getLogger(__name__)


class TradingEngineWorker(QObject):
    """QObject worker managing MT5 polling, orders, and analysis via signals."""

    account_updated = Signal(object)        # AccountInfo
    positions_updated = Signal(list)        # list[Position]
    analysis_completed = Signal(object)     # MarketAnalysisReport
    log_emitted = Signal(str, str)          # message, level ("INFO", "WARNING", "ERROR", "TRADE")
    status_message = Signal(str)            # status text

    def __init__(
        self,
        bridge: MT5Bridge | None = None,
        simulation: bool = True,
        poll_interval_ms: int = 3000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.simulation = simulation
        self.poll_interval_ms = poll_interval_ms
        self.bridge = bridge or MT5Bridge(simulation=simulation)
        self.circuit_breaker = CircuitBreaker()
        self.autotrade_enabled = True
        self._poll_timer: QTimer | None = None

    def start_polling(self) -> None:
        """Start the periodic polling timer for account & active positions."""
        self.bridge.connect()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self.poll_account_and_positions)
        self._poll_timer.start(self.poll_interval_ms)
        self.log_emitted.emit(f"Engine worker started (Simulation={self.bridge.simulation})", "INFO")
        self.poll_account_and_positions()

    def stop_polling(self) -> None:
        """Stop periodic timer and disconnect."""
        if self._poll_timer:
            self._poll_timer.stop()
        self.bridge.disconnect()
        self.log_emitted.emit("Engine worker stopped.", "INFO")

    def poll_account_and_positions(self) -> None:
        """Fetch latest account info and positions from MT5 bridge."""
        try:
            acc = self.bridge.get_account_info()
            positions = self.bridge.get_open_positions()
            self.account_updated.emit(acc)
            self.positions_updated.emit(positions)
        except Exception as err:
            logger.exception("Error polling MT5")
            self.log_emitted.emit(f"Error polling MT5: {err}", "ERROR")

    def execute_manual_order(self, symbol: str, order_type: str, volume: float) -> None:
        """Execute manual Buy/Sell order requested by GUI."""
        try:
            self.log_emitted.emit(f"Executing manual {order_type} {volume} lots on {symbol}...", "INFO")
            ticket = self.bridge.send_market_order(
                symbol=symbol,
                order_type=order_type,
                volume=volume,
                comment="DareFX GUI Manual",
            )
            if ticket:
                self.log_emitted.emit(f"Manual {order_type} executed successfully! Ticket: #{ticket}", "TRADE")
            else:
                self.log_emitted.emit(f"Manual {order_type} failed at broker.", "ERROR")
            self.poll_account_and_positions()
        except Exception as err:
            self.log_emitted.emit(f"Manual order exception: {err}", "ERROR")

    def close_position(self, ticket: int) -> None:
        """Close an individual position by ticket."""
        try:
            self.log_emitted.emit(f"Closing position #{ticket}...", "INFO")
            success = self.bridge.close_position(ticket=ticket)
            if success:
                self.log_emitted.emit(f"Position #{ticket} closed successfully.", "TRADE")
            else:
                self.log_emitted.emit(f"Failed to close position #{ticket}.", "ERROR")
            self.poll_account_and_positions()
        except Exception as err:
            self.log_emitted.emit(f"Close position #{ticket} error: {err}", "ERROR")

    def panic_close_all(self) -> None:
        """Emergency liquidation of all open positions."""
        try:
            positions = self.bridge.get_open_positions()
            if not positions:
                self.log_emitted.emit("No open positions to close.", "INFO")
                return
            self.log_emitted.emit(f"PANIC CLOSE ALL: Liquidating {len(positions)} positions...", "WARNING")
            for pos in positions:
                self.bridge.close_position(pos.ticket)
            self.log_emitted.emit("Panic close all completed.", "WARNING")
            self.poll_account_and_positions()
        except Exception as err:
            self.log_emitted.emit(f"Panic close error: {err}", "ERROR")

    def run_market_analysis(self, symbol: str = "EURUSD") -> None:
        """Run deep technical and ML analysis in thread."""
        try:
            self.log_emitted.emit(f"Running AI Market Analysis for {symbol}...", "INFO")
            analyzer = MarketAnalyzer(symbol=symbol)
            report = analyzer.analyze(fetch_live=True)
            self.analysis_completed.emit(report)
            self.log_emitted.emit(f"AI Analysis completed: {report.recommendation} ({report.confidence*100:.1f}%)", "INFO")
        except Exception as err:
            self.log_emitted.emit(f"AI Analysis error: {err}", "ERROR")

    def set_autotrade(self, enabled: bool) -> None:
        """Toggle autotrade state."""
        self.autotrade_enabled = enabled
        status_text = "ENABLED" if enabled else "DISABLED"
        self.log_emitted.emit(f"Autotrade mode changed to: {status_text}", "INFO")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_gui_worker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/darefx/gui/worker.py tests/test_gui_worker.py
git commit -m "feat(gui): implement TradingEngineWorker with Qt signals and execution methods"
```

---

### Task 4: UI Components (Metric Cards, Positions Table, Control Panel, Analysis Panel)

**Files:**
- Create: `src/darefx/gui/components/__init__.py`
- Create: `src/darefx/gui/components/metric_card.py`
- Create: `src/darefx/gui/components/positions_table.py`
- Create: `src/darefx/gui/components/control_panel.py`
- Create: `src/darefx/gui/components/analysis_panel.py`
- Test: `tests/test_gui_components.py`

**Interfaces:**
- Consumes: `ThemeColors`, `get_badge_style`, `AccountInfo`, `Position`, `MarketAnalysisReport`
- Produces: Reusable widgets: `MetricCard`, `PositionsTableWidget`, `ControlPanelWidget`, `AnalysisPanelWidget`

- [ ] **Step 1: Write failing test for UI components**

Create `tests/test_gui_components.py`:
```python
import os
import pytest
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication
from darefx.gui.components.metric_card import MetricCard
from darefx.gui.components.positions_table import PositionsTableWidget
from darefx.gui.components.control_panel import ControlPanelWidget
from darefx.trading.mt5_bridge import Position
from datetime import datetime, timezone

@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app

def test_metric_card_update(qapp) -> None:
    card = MetricCard("Equity", "$94,320.50", "Floating: +$1,220.00", is_positive=True)
    assert card.title_label.text() == "Equity"
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
            pips=50.0,
            open_time=datetime.now(timezone.utc),
        )
    ]
    table.update_positions(test_positions)
    assert table.rowCount() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_gui_components.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'darefx.gui.components'`

- [ ] **Step 3: Create components directory and implement widgets**

Create `src/darefx/gui/components/__init__.py`:
```python
"""DareFX GUI UI Components."""
```

Create `src/darefx/gui/components/metric_card.py`:
```python
"""Clean metric summary card widget."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from darefx.gui.styles import ThemeColors


class MetricCard(QFrame):
    """Clean financial metric card displaying title, primary value, and subtitle."""

    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
        is_positive: bool | None = None,
        parent: QFrame | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "metricCard")
        self.setObjectName("MetricCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {ThemeColors.TEXT_PRIMARY}; font-size: 20px; font-weight: 700;")

        self.subtitle_label = QLabel(subtitle)
        self._apply_subtitle_color(is_positive)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)

    def _apply_subtitle_color(self, is_positive: bool | None) -> None:
        if is_positive is True:
            color = ThemeColors.ACCENT_SUCCESS
        elif is_positive is False:
            color = ThemeColors.ACCENT_DANGER
        else:
            color = ThemeColors.TEXT_MUTED
        self.subtitle_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 500;")

    def update_values(self, value: str, subtitle: str = "", is_positive: bool | None = None) -> None:
        self.value_label.setText(value)
        self.subtitle_label.setText(subtitle)
        self._apply_subtitle_color(is_positive)
```

Create `src/darefx/gui/components/positions_table.py`:
```python
"""Live positions table with action buttons."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from darefx.gui.styles import ThemeColors, get_badge_style
from darefx.trading.mt5_bridge import Position


class PositionsTableWidget(QTableWidget):
    """Table widget showing real-time MT5 orders with action buttons."""

    close_requested = Signal(int)  # ticket

    COLUMNS = [
        "Tiket", "Symbol", "Tipe", "Lots", "Harga Buka", "Harga Saat Ini",
        "SL", "TP", "Profit ($)", "Pips", "Proteksi BE", "Aksi"
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(11, QHeaderView.ResizeMode.ResizeToContents)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)

    def update_positions(self, positions: list[Position]) -> None:
        """Refresh table rows from active MT5 positions."""
        self.setRowCount(len(positions))
        for row, pos in enumerate(positions):
            # Ticket
            item_ticket = QTableWidgetItem(f"#{pos.ticket}")
            item_ticket.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 0, item_ticket)

            # Symbol
            item_sym = QTableWidgetItem(pos.symbol)
            item_sym.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 1, item_sym)

            # Type Badge
            type_label = QLabel(pos.order_type)
            type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            type_label.setStyleSheet(get_badge_style(pos.order_type))
            self.setCellWidget(row, 2, type_label)

            # Lots
            item_lots = QTableWidgetItem(f"{pos.volume:.2f}")
            item_lots.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(row, 3, item_lots)

            # Open Price
            item_open = QTableWidgetItem(f"{pos.open_price:.5f}")
            item_open.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(row, 4, item_open)

            # Current Price
            item_curr = QTableWidgetItem(f"{pos.current_price:.5f}")
            item_curr.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(row, 5, item_curr)

            # SL / TP
            self.setItem(row, 6, QTableWidgetItem(f"{pos.sl:.5f}" if pos.sl > 0 else "-"))
            self.setItem(row, 7, QTableWidgetItem(f"{pos.tp:.5f}" if pos.tp > 0 else "-"))

            # Profit ($)
            profit_prefix = "+" if pos.profit > 0 else ""
            item_profit = QTableWidgetItem(f"{profit_prefix}${pos.profit:.2f}")
            profit_color = ThemeColors.ACCENT_SUCCESS if pos.profit >= 0 else ThemeColors.ACCENT_DANGER
            item_profit.setForeground(Qt.GlobalColor.darkGreen if pos.profit >= 0 else Qt.GlobalColor.darkRed)
            item_profit.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(row, 8, item_profit)

            # Pips
            item_pips = QTableWidgetItem(f"{pos.pips:+.1f} pips")
            item_pips.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(row, 9, item_pips)

            # BE Status
            is_be = (pos.order_type == "BUY" and pos.sl >= pos.open_price) or (
                pos.order_type == "SELL" and pos.sl > 0 and pos.sl <= pos.open_price
            )
            be_text = "AKTIF (BE+)" if is_be else "STANDBY"
            be_badge = QLabel(be_text)
            be_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            be_badge.setStyleSheet(get_badge_style("active" if is_be else "neutral"))
            self.setCellWidget(row, 10, be_badge)

            # Action button: Close
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            close_btn = QPushButton("Tutup")
            close_btn.setProperty("class", "dangerBtn")
            close_btn.clicked.connect(lambda checked=False, t=pos.ticket: self.close_requested.emit(t))
            btn_layout.addWidget(close_btn)
            self.setCellWidget(row, 11, btn_container)
```

Create `src/darefx/gui/components/control_panel.py`:
```python
"""Master Control Toolbar with safety confirmations."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)


class ControlPanelWidget(QFrame):
    """Quick control panel for Autotrade toggle, Panic Close, and Manual Orders."""

    autotrade_toggled = Signal(bool)
    panic_close_requested = Signal()
    manual_order_requested = Signal(str, float)  # order_type, lots
    run_analysis_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "metricCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Autotrade toggle
        self.autotrade_btn = QPushButton("🟢 Auto-Trade: AKTIF")
        self.autotrade_btn.setProperty("class", "successBtn")
        self.autotrade_btn.setCheckable(True)
        self.autotrade_btn.setChecked(True)
        self.autotrade_btn.clicked.connect(self._handle_autotrade_click)
        layout.addWidget(self.autotrade_btn)

        # Panic Close All
        self.panic_btn = QPushButton("🚨 Tutup Semua Posisi")
        self.panic_btn.setProperty("class", "dangerBtn")
        self.panic_btn.clicked.connect(self._handle_panic_close_click)
        layout.addWidget(self.panic_btn)

        layout.addSpacing(20)

        # Manual Trade Section
        layout.addWidget(QLabel("Manual Lot:"))
        self.lot_spinbox = QDoubleSpinBox()
        self.lot_spinbox.setRange(0.01, 10.0)
        self.lot_spinbox.setSingleStep(0.01)
        self.lot_spinbox.setValue(0.10)
        self.lot_spinbox.setDecimals(2)
        layout.addWidget(self.lot_spinbox)

        self.buy_btn = QPushButton("⚡ Beli (BUY)")
        self.buy_btn.setProperty("class", "successBtn")
        self.buy_btn.clicked.connect(lambda: self.manual_order_requested.emit("BUY", self.lot_spinbox.value()))
        layout.addWidget(self.buy_btn)

        self.sell_btn = QPushButton("⚡ Jual (SELL)")
        self.sell_btn.setProperty("class", "dangerBtn")
        self.sell_btn.clicked.connect(lambda: self.manual_order_requested.emit("SELL", self.lot_spinbox.value()))
        layout.addWidget(self.sell_btn)

        layout.addStretch()

        # Run Analysis Button
        self.analysis_btn = QPushButton("🤖 Analisis AI Pasar")
        self.analysis_btn.setProperty("class", "primaryBtn")
        self.analysis_btn.clicked.connect(self.run_analysis_requested.emit)
        layout.addWidget(self.analysis_btn)

    def _handle_autotrade_click(self) -> None:
        is_active = self.autotrade_btn.isChecked()
        if is_active:
            self.autotrade_btn.setText("🟢 Auto-Trade: AKTIF")
            self.autotrade_btn.setProperty("class", "successBtn")
        else:
            self.autotrade_btn.setText("🔴 Auto-Trade: NONAKTIF")
            self.autotrade_btn.setProperty("class", "dangerBtn")
        self.autotrade_btn.style().unpolish(self.autotrade_btn)
        self.autotrade_btn.style().polish(self.autotrade_btn)
        self.autotrade_toggled.emit(is_active)

    def _handle_panic_close_click(self) -> None:
        reply = QMessageBox.question(
            self,
            "Konfirmasi Likuidasi Posisi",
            "Apakah Anda yakin ingin SEGERA menutup SEMUA posisi aktif saat ini?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.panic_close_requested.emit()
```

Create `src/darefx/gui/components/analysis_panel.py`:
```python
"""AI Market Analysis Report Display Panel."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from darefx.analysis.market_analyzer import MarketAnalysisReport
from darefx.gui.styles import ThemeColors, get_badge_style


class AnalysisPanelWidget(QFrame):
    """Panel displaying AI signals, LightGBM probabilities, and technical regime."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "metricCard")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # Title & Recommendation Badge
        header_layout = QHBoxLayout()
        header_title = QLabel("HASIL ANALISIS AI & REGIME PASAR")
        header_title.setStyleSheet(f"font-weight: 700; color: {ThemeColors.TEXT_PRIMARY}; font-size: 13px;")
        self.rec_badge = QLabel("MENUNGGU ANALISIS...")
        self.rec_badge.setStyleSheet(get_badge_style("neutral"))

        header_layout.addWidget(header_title)
        header_layout.addStretch()
        header_layout.addWidget(self.rec_badge)
        main_layout.addLayout(header_layout)

        # Grid of metrics
        grid = QGridLayout()
        grid.setSpacing(8)

        self.lbl_price = QLabel("Harga: -")
        self.lbl_trend = QLabel("Tren: -")
        self.lbl_adx = QLabel("ADX (14): -")
        self.lbl_rsi = QLabel("RSI (14): -")
        self.lbl_atr = QLabel("ATR: -")
        self.lbl_lots = QLabel("Saran Lot: -")

        grid.addWidget(self.lbl_price, 0, 0)
        grid.addWidget(self.lbl_trend, 0, 1)
        grid.addWidget(self.lbl_adx, 1, 0)
        grid.addWidget(self.lbl_rsi, 1, 1)
        grid.addWidget(self.lbl_atr, 2, 0)
        grid.addWidget(self.lbl_lots, 2, 1)
        main_layout.addLayout(grid)

        # Probabilities Bar
        prob_title = QLabel("Probabilitas Model AI (LightGBM):")
        prob_title.setStyleSheet(f"font-size: 11px; color: {ThemeColors.TEXT_MUTED}; font-weight: 600;")
        main_layout.addWidget(prob_title)

        self.prob_label = QLabel("BUY: 0.0%  |  NETRAL: 0.0%  |  SELL: 0.0%")
        self.prob_label.setStyleSheet("font-family: monospace; font-size: 11px;")
        main_layout.addWidget(self.prob_label)

        self.reasoning_label = QLabel("Tekan tombol '🤖 Analisis AI Pasar' untuk memindai kondisi pasar terbaru.")
        self.reasoning_label.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 11px; font-style: italic;")
        self.reasoning_label.setWordWrap(True)
        main_layout.addWidget(self.reasoning_label)

    def update_report(self, report: MarketAnalysisReport) -> None:
        """Render fresh analysis report."""
        self.rec_badge.setText(f"{report.recommendation} ({report.confidence * 100:.1f}%)")
        self.rec_badge.setStyleSheet(get_badge_style(report.recommendation))

        self.lbl_price.setText(f"Harga: <b>{report.current_price:.5f}</b> ({report.pips_change:+.1f} pips)")
        self.lbl_trend.setText(f"Tren: <b>{report.trend_bias}</b>")
        self.lbl_adx.setText(f"ADX: <b>{report.adx_14:.1f}</b> ({report.adx_condition})")
        self.lbl_rsi.setText(f"RSI: <b>{report.rsi_14:.1f}</b> ({report.rsi_condition})")
        self.lbl_atr.setText(f"ATR: <b>{report.atr_pips:.1f} pips</b>")
        self.lbl_lots.setText(f"Saran Lot: <b>{report.recommended_lots:.2f} lot</b>")

        self.prob_label.setText(
            f"BUY: {report.prob_buy * 100:.1f}%   |   "
            f"NETRAL: {report.prob_neutral * 100:.1f}%   |   "
            f"SELL: {report.prob_sell * 100:.1f}%"
        )
        self.reasoning_label.setText(f"💡 <b>Keterangan:</b> {report.reasoning}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_gui_components.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/darefx/gui/components/ tests/test_gui_components.py
git commit -m "feat(gui): build metric card, positions table, control panel, and analysis panel"
```

---

### Task 5: Settings Dialog & Configuration Persistence (`src/darefx/gui/components/settings_dialog.py`)

**Files:**
- Create: `src/darefx/gui/components/settings_dialog.py`
- Test: `tests/test_gui_settings.py`

**Interfaces:**
- Consumes: `.env` file path, `python-dotenv`
- Produces: `SettingsDialog(QDialog)` with form validation and persistence

- [ ] **Step 1: Write failing test for settings dialog logic**

Create `tests/test_gui_settings.py`:
```python
import os
import tempfile
from pathlib import Path
import pytest
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication
from darefx.gui.components.settings_dialog import SettingsDialog, load_env_values, save_env_values

@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app

def test_save_and_load_env_values() -> None:
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        f.write("RISK_PER_TRADE_PCT=0.015\nBE_TRIGGER_PIPS=15.0\nAUTO_TRADE=true\n")
        env_path = Path(f.name)

    values = load_env_values(env_path)
    assert values["RISK_PER_TRADE_PCT"] == "0.015"
    assert values["BE_TRIGGER_PIPS"] == "15.0"

    save_env_values(env_path, {"RISK_PER_TRADE_PCT": "0.02", "BE_TRIGGER_PIPS": "20.0"})
    updated = load_env_values(env_path)
    assert updated["RISK_PER_TRADE_PCT"] == "0.02"
    assert updated["BE_TRIGGER_PIPS"] == "20.0"
    env_path.unlink()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_gui_settings.py -v`
Expected: FAIL with `ImportError: cannot import name 'SettingsDialog'`

- [ ] **Step 3: Implement SettingsDialog and env helper functions**

Create `src/darefx/gui/components/settings_dialog.py`:
```python
"""Settings configuration dialog with .env persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from darefx.gui.styles import ThemeColors


def load_env_values(env_path: Path) -> dict[str, str]:
    """Parse key-value pairs from .env file."""
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip("'\"")
    return values


def save_env_values(env_path: Path, new_values: dict[str, str]) -> None:
    """Update or append key-value pairs in .env while preserving unrelated lines."""
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    updated_keys = set()
    new_lines: list[str] = []

    for line in existing_lines:
        trimmed = line.strip()
        if trimmed and not trimmed.startswith("#") and "=" in trimmed:
            k, _ = trimmed.split("=", 1)
            key = k.strip()
            if key in new_values:
                new_lines.append(f"{key}={new_values[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    for k, v in new_values.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class SettingsDialog(QDialog):
    """Dialog for editing trading and risk parameters directly from GUI."""

    def __init__(self, env_path: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pengaturan Parameter DareFX")
        self.resize(450, 380)
        self.env_path = env_path or Path(".env")
        self.current_values = load_env_values(self.env_path)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)

        header = QLabel("Konfigurasi Parameter Trading & Risiko")
        header.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {ThemeColors.TEXT_PRIMARY};")
        main_layout.addWidget(header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Risk per Trade %
        self.spin_risk = QDoubleSpinBox()
        self.spin_risk.setRange(0.1, 10.0)
        self.spin_risk.setSingleStep(0.1)
        self.spin_risk.setValue(float(self.current_values.get("RISK_PER_TRADE_PCT", "0.01")) * 100.0)
        self.spin_risk.setSuffix(" %")
        form.addRow("Risiko per Trade:", self.spin_risk)

        # BE Trigger Pips
        self.spin_be = QDoubleSpinBox()
        self.spin_be.setRange(5.0, 100.0)
        self.spin_be.setSingleStep(1.0)
        self.spin_be.setValue(float(self.current_values.get("BE_TRIGGER_PIPS", "15.0")))
        self.spin_be.setSuffix(" pips")
        form.addRow("Trigger Break-Even:", self.spin_be)

        # Confidence Threshold AI
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.30, 0.90)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(float(self.current_values.get("CONFIDENCE_THRESHOLD", "0.40")))
        form.addRow("AI Threshold (Min Conf):", self.spin_conf)

        # Symbol
        self.txt_symbol = QLineEdit(self.current_values.get("SYMBOL", "EURUSD"))
        form.addRow("Pasangan Mata Uang:", self.txt_symbol)

        # Auto-Trade Default
        self.chk_autotrade = QCheckBox("Aktifkan Auto-Trade saat bot pertama kali menyala")
        self.chk_autotrade.setChecked(self.current_values.get("AUTO_TRADE", "true").lower() == "true")
        form.addRow("Auto-Trade Awal:", self.chk_autotrade)

        main_layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Simpan & Terapkan")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self._handle_save)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    def _handle_save(self) -> None:
        try:
            updates = {
                "RISK_PER_TRADE_PCT": f"{self.spin_risk.value() / 100.0:.4f}",
                "BE_TRIGGER_PIPS": f"{self.spin_be.value():.1f}",
                "CONFIDENCE_THRESHOLD": f"{self.spin_conf.value():.2f}",
                "SYMBOL": self.txt_symbol.text().strip().upper(),
                "AUTO_TRADE": "true" if self.chk_autotrade.isChecked() else "false",
            }
            save_env_values(self.env_path, updates)
            QMessageBox.information(self, "Pengaturan Tersimpan", "Konfigurasi berhasil disimpan ke file .env!")
            self.accept()
        except Exception as err:
            QMessageBox.critical(self, "Gagal Menyimpan", f"Terjadi kesalahan saat menyimpan: {err}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_gui_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/darefx/gui/components/settings_dialog.py tests/test_gui_settings.py
git commit -m "feat(gui): implement SettingsDialog with .env persistence"
```

---

### Task 6: Main Window, System Tray & Application Assembly (`src/darefx/gui/main_window.py`)

**Files:**
- Create: `src/darefx/gui/main_window.py`
- Test: `tests/test_gui_main_window.py`

**Interfaces:**
- Consumes: All UI components, `TradingEngineWorker`, `get_application_stylesheet()`
- Produces: `DareFXMainWindow(QMainWindow)`

- [ ] **Step 1: Write failing test for DareFXMainWindow**

Create `tests/test_gui_main_window.py`:
```python
import os
import pytest
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication
from darefx.gui.main_window import DareFXMainWindow

@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app

def test_main_window_initialization(qapp) -> None:
    window = DareFXMainWindow(simulation=True)
    assert window.windowTitle() == "DareFX — AI Algorithmic Trading Terminal"
    assert window.worker is not None
    assert window.metric_balance is not None
    assert window.positions_table is not None
    assert window.control_panel is not None
    window.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_gui_main_window.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'darefx.gui.main_window'`

- [ ] **Step 3: Implement DareFXMainWindow**

Create `src/darefx/gui/main_window.py`:
```python
"""Main Window for DareFX Desktop Terminal."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from darefx.analysis.market_analyzer import MarketAnalysisReport
from darefx.gui.components.analysis_panel import AnalysisPanelWidget
from darefx.gui.components.control_panel import ControlPanelWidget
from darefx.gui.components.metric_card import MetricCard
from darefx.gui.components.positions_table import PositionsTableWidget
from darefx.gui.components.settings_dialog import SettingsDialog
from darefx.gui.styles import ThemeColors, get_application_stylesheet, get_badge_style
from darefx.gui.worker import TradingEngineWorker
from darefx.trading.mt5_bridge import AccountInfo, Position

logger = logging.getLogger(__name__)


class DareFXMainWindow(QMainWindow):
    """Primary enterprise desktop window for DareFX trading terminal."""

    def __init__(self, simulation: bool = False, env_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("DareFX — AI Algorithmic Trading Terminal")
        self.resize(1180, 820)
        self.setStyleSheet(get_application_stylesheet())
        self.env_path = env_path or Path(".env")

        # Worker & Background Thread
        self.thread = QThread()
        self.worker = TradingEngineWorker(simulation=simulation)
        self.worker.moveToThread(self.thread)

        self._build_ui()
        self._setup_system_tray()
        self._connect_signals()

        # Start thread
        self.thread.started.connect(self.worker.start_polling)
        self.thread.start()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(12)

        # 1. Header Toolbar
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        app_title = QLabel("DareFX Quantitative Trading Station")
        app_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {ThemeColors.TEXT_PRIMARY};")
        subtitle = QLabel("EUR/USD Triple-Barrier AI Execution Engine")
        subtitle.setStyleSheet(f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};")
        title_box.addWidget(app_title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        self.status_badge = QLabel("MT5: MENGHUBUNGKAN...")
        self.status_badge.setStyleSheet(get_badge_style("warning"))
        header_layout.addWidget(self.status_badge)

        self.settings_btn = QPushButton("⚙️ Pengaturan")
        self.settings_btn.clicked.connect(self._open_settings)
        header_layout.addWidget(self.settings_btn)

        root_layout.addLayout(header_layout)

        # 2. Financial Metrics Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)
        self.metric_balance = MetricCard("Balance (Saldo)", "$0.00", "Akun Terverifikasi")
        self.metric_equity = MetricCard("Equity (Ekuitas)", "$0.00", "Floating: $0.00")
        self.metric_positions = MetricCard("Posisi Terbuka", "0 Order", "Batas Margin Aman")
        self.metric_daily_pnl = MetricCard("PnL Harian", "+$0.00", "Status Sirkuit: AKTIF", is_positive=True)

        metrics_layout.addWidget(self.metric_balance)
        metrics_layout.addWidget(self.metric_equity)
        metrics_layout.addWidget(self.metric_positions)
        metrics_layout.addWidget(self.metric_daily_pnl)
        root_layout.addLayout(metrics_layout)

        # 3. Quick Control Toolbar
        self.control_panel = ControlPanelWidget()
        root_layout.addWidget(self.control_panel)

        # 4. Main Body Splitter: Positions Table (Top) & Split AI / Log (Bottom)
        body_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top: Positions Table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_header = QLabel("POSISI AKTIF & PROTEKSI BREAK-EVEN (MT5 LIVE)")
        table_header.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_MUTED};")
        table_layout.addWidget(table_header)
        self.positions_table = PositionsTableWidget()
        table_layout.addWidget(self.positions_table)
        body_splitter.addWidget(table_container)

        # Bottom Splitter: AI Analysis (Left) + Log Console (Right)
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.analysis_panel = AnalysisPanelWidget()
        bottom_splitter.addWidget(self.analysis_panel)

        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_header = QLabel("LOG EKSEKUSI & AUDIT BOT")
        log_header.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_MUTED};")
        log_layout.addWidget(log_header)

        self.log_console = QTextEdit()
        self.log_console.setObjectName("LogConsole")
        self.log_console.setReadOnly(True)
        log_layout.addWidget(self.log_console)
        bottom_splitter.addWidget(log_container)

        bottom_splitter.setSizes([500, 500])
        body_splitter.addWidget(bottom_splitter)
        body_splitter.setSizes([380, 320])

        root_layout.addWidget(body_splitter)

    def _setup_system_tray(self) -> None:
        """Create system tray icon and background minimize support."""
        self.tray_icon = QSystemTrayIcon(self)
        # Use fallback standard icon if no asset file
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("DareFX Trading Station (Running)")

        tray_menu = self.tray_icon.contextMenu() or QWidget()
        action_restore = QAction("Buka Window", self)
        action_restore.triggered.connect(self.showNormal)
        action_exit = QAction("Keluar Aplikasi", self)
        action_exit.triggered.connect(self._force_quit)

        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        menu.addAction(action_restore)
        menu.addSeparator()
        menu.addAction(action_exit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _connect_signals(self) -> None:
        # Worker to UI
        self.worker.account_updated.connect(self._on_account_updated)
        self.worker.positions_updated.connect(self._on_positions_updated)
        self.worker.analysis_completed.connect(self.analysis_panel.update_report)
        self.worker.log_emitted.connect(self._append_log)

        # UI to Worker
        self.control_panel.autotrade_toggled.connect(self.worker.set_autotrade)
        self.control_panel.panic_close_requested.connect(self.worker.panic_close_all)
        self.control_panel.manual_order_requested.connect(
            lambda o_type, lot: self.worker.execute_manual_order("EURUSD", o_type, lot)
        )
        self.control_panel.run_analysis_requested.connect(lambda: self.worker.run_market_analysis("EURUSD"))
        self.positions_table.close_requested.connect(self.worker.close_position)

    def _on_account_updated(self, acc: AccountInfo) -> None:
        self.metric_balance.update_values(f"${acc.balance:,.2f}", f"Leverage 1:{acc.leverage}")
        floating = acc.equity - acc.balance
        floating_sign = "+" if floating >= 0 else ""
        self.metric_equity.update_values(
            f"${acc.equity:,.2f}",
            f"Floating: {floating_sign}${floating:,.2f}",
            is_positive=(floating >= 0),
        )
        mode_str = "SIMULASI" if self.worker.bridge.simulation else f"LIVE ({acc.login})"
        self.status_badge.setText(f"MT5: {mode_str}")
        self.status_badge.setStyleSheet(get_badge_style("active" if not self.worker.bridge.simulation else "warning"))

    def _on_positions_updated(self, positions: list[Position]) -> None:
        self.positions_table.update_positions(positions)
        total_profit = sum(p.profit for p in positions)
        total_pips = sum(p.pips for p in positions)
        profit_sign = "+" if total_profit >= 0 else ""
        self.metric_positions.update_values(
            f"{len(positions)} Order",
            f"Net: {profit_sign}${total_profit:.2f} ({total_pips:+.1f} p)",
            is_positive=(total_profit >= 0) if positions else None,
        )

    def _append_log(self, message: str, level: str) -> None:
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        color_map = {
            "INFO": ThemeColors.TEXT_MUTED,
            "TRADE": ThemeColors.ACCENT_SUCCESS,
            "WARNING": ThemeColors.ACCENT_WARNING,
            "ERROR": ThemeColors.ACCENT_DANGER,
        }
        color = color_map.get(level, ThemeColors.TEXT_PRIMARY)
        formatted = f"<span style='color:{ThemeColors.TEXT_MUTED};'>[{now_str}]</span> <span style='color:{color}; font-weight:600;'>[{level}]</span> {message}"
        self.log_console.append(formatted)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(env_path=self.env_path, parent=self)
        dlg.exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Minimize to tray instead of quitting."""
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "DareFX Trading Terminal",
                "Aplikasi berjalan di background (System Tray). Bot tetap mengawal order Anda.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            event.ignore()
        else:
            self._force_quit()

    def _force_quit(self) -> None:
        self.worker.stop_polling()
        self.thread.quit()
        self.thread.wait(2000)
        self.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_gui_main_window.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/darefx/gui/main_window.py tests/test_gui_main_window.py
git commit -m "feat(gui): assemble DareFXMainWindow with system tray and real-time data flows"
```

---

### Task 7: Entry Point Script & Windows Desktop Shortcut Creator (`app.py` & PowerShell)

**Files:**
- Create: `app.py`
- Create: `scripts/create_desktop_shortcut.ps1`
- Test: `tests/test_gui_app_entry.py`

**Interfaces:**
- Consumes: `DareFXMainWindow`, `sys.argv`
- Produces: `app.py` executable script, Windows Desktop Shortcut generator

- [ ] **Step 1: Write test for app module imports**

Create `tests/test_gui_app_entry.py`:
```python
import importlib

def test_app_entry_module_is_importable() -> None:
    mod = importlib.import_module("app")
    assert hasattr(mod, "main")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_gui_app_entry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Implement `app.py` and Windows shortcut creator**

Create `app.py`:
```python
"""DareFX Native Desktop GUI Application Entrypoint."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

from PySide6.QtWidgets import QApplication
from darefx.gui.main_window import DareFXMainWindow

def main() -> None:
    # Load environment variables
    load_dotenv()
    simulation = os.getenv("MT5_SIMULATION", "false").lower() == "true"

    app = QApplication(sys.argv)
    app.setApplicationName("DareFX Trading Station")
    app.setOrganizationName("DareFX")

    window = DareFXMainWindow(simulation=simulation)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

Create `scripts/create_desktop_shortcut.ps1`:
```powershell
# PowerShell script to create a clean Desktop Shortcut for DareFX GUI using pythonw.exe
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$ShortcutPath = Join-Path $DesktopPath "DareFX Trading Terminal.lnk"

$ProjectRoot = "C:\DareFX"
$PythonW = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$TargetScript = Join-Path $ProjectRoot "app.py"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = "`"$TargetScript`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "DareFX Quantitative AI Trading Terminal"
$Shortcut.Save()

Write-Host "✅ Desktop shortcut created successfully at: $ShortcutPath"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_gui_app_entry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py scripts/create_desktop_shortcut.ps1 tests/test_gui_app_entry.py
git commit -m "feat(gui): add app.py launcher and Windows Desktop shortcut generator"
```

---

### Task 8: Full Regression Suite & CI Verification

**Files:**
- Modify: `.github/workflows/ci.yml:30-36` (if necessary to ensure pytest passes headless)
- Test: All tests in `tests/`

- [ ] **Step 1: Run full test suite with headless Qt flag**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v`
Expected: 100% PASS across all existing and new GUI unit tests.

- [ ] **Step 2: Verify git status and commit any remaining changes**

Run: `git status`
Expected: Clean working tree.

- [ ] **Step 3: Push to remote GitHub repository**

Run: `git push origin main`
Expected: Push succeeds and triggers GitHub Actions CI.

- [ ] **Step 4: Verify GitHub Actions CI Run completes green**

Run: `gh run watch <run-id>`
Expected: ✓ Run CI completed with 'success'.
