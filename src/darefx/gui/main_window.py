"""Main Window for DareFX Desktop Terminal."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSplitter,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from darefx.analysis.market_analyzer import MarketAnalysisReport
from darefx.gui.components.analysis_panel import AnalysisPanelWidget
from darefx.gui.components.control_panel import ControlPanelWidget
from darefx.gui.components.crypto_panel import CryptoPanelWidget
from darefx.gui.components.metric_card import MetricCard
from darefx.gui.components.positions_table import PositionsTableWidget
from darefx.gui.components.screener_table import ScreenerTableWidget
from darefx.gui.components.settings_dialog import SettingsDialog
from darefx.gui.components.stock_panel import StockPanelWidget
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
        self.tray_icon: QSystemTrayIcon | None = None

        # Set application and window icon
        logo_icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo" / "darefx-app.png"
        if not logo_icon_path.exists():
            logo_icon_path = Path("assets/logo/darefx-app.png")
        if logo_icon_path.exists():
            self.setWindowIcon(QIcon(str(logo_icon_path)))

        # Worker & Background Thread
        self.thread = QThread()
        self.worker = TradingEngineWorker(simulation=simulation)
        self.worker.moveToThread(self.thread)

        self._build_ui()
        if QSystemTrayIcon.isSystemTrayAvailable():
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

        # 1. Header Toolbar with Logo Mark
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo" / "darefx-app.png"
        if not logo_path.exists():
            logo_path = Path("assets/logo/darefx-app.png")
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path)).scaled(
                40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(pixmap)
            header_layout.addWidget(logo_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
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

        self.exit_btn = QPushButton("🚪 Keluar")
        self.exit_btn.setProperty("class", "dangerBtn")
        self.exit_btn.setToolTip("Tutup dan keluar dari aplikasi (Ctrl+Q)")
        self.exit_btn.clicked.connect(self._force_quit)
        header_layout.addWidget(self.exit_btn)

        # Global shortcut Ctrl+Q to quit
        QShortcut(QKeySequence("Ctrl+Q"), self, self._force_quit)

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

        # 3. Main Multi-Asset Tabbed Cockpit
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainCockpitTabs")

        # --- Tab 1: Overview & Forex Terminal (MT5) ---
        forex_tab = QWidget()
        forex_layout = QVBoxLayout(forex_tab)
        forex_layout.setContentsMargins(6, 10, 6, 6)
        forex_layout.setSpacing(10)

        self.control_panel = ControlPanelWidget()
        forex_layout.addWidget(self.control_panel)

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

        forex_layout.addWidget(body_splitter)
        self.tabs.addTab(forex_tab, "📊 Overview & Forex (MT5)")

        # --- Tab 2: Crypto Terminal (CCXT) ---
        self.crypto_panel = CryptoPanelWidget()
        self.tabs.addTab(self.crypto_panel, "🪙 Crypto Terminal (CCXT)")

        # --- Tab 3: Stocks Terminal (Equities) ---
        self.stock_panel = StockPanelWidget()
        self.tabs.addTab(self.stock_panel, "🏛️ Stocks Terminal (Equities)")

        # --- Tab 4: Market Screener ---
        self.screener_panel = ScreenerTableWidget()
        self.tabs.addTab(self.screener_panel, "🔍 Market Screener")

        root_layout.addWidget(self.tabs)

    def _setup_system_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo" / "darefx-app.png"
        if not logo_path.exists():
            logo_path = Path("assets/logo/darefx-app.png")
        if logo_path.exists():
            self.tray_icon.setIcon(QIcon(str(logo_path)))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("DareFX Trading Station (Running)")

        menu = QMenu()
        action_restore = QAction("Buka Window", self)
        action_restore.triggered.connect(self.showNormal)
        action_exit = QAction("Keluar Aplikasi", self)
        action_exit.triggered.connect(self._force_quit)

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
        mode_str = "SIMULASI" if self.worker.is_simulation else f"LIVE ({acc.login})"
        self.status_badge.setText(f"MT5: {mode_str}")
        self.status_badge.setStyleSheet(get_badge_style("active" if not self.worker.is_simulation else "warning"))

    def _on_positions_updated(self, positions: list[Position]) -> None:
        self.positions_table.update_positions(positions)
        total_profit = sum(p.profit for p in positions)
        total_pips = sum(
            ((p.open_price - p.current_price) if str(p.order_type).upper().endswith("SELL") else (p.current_price - p.open_price)) / 0.0001
            for p in positions
        )
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
        """Close window and cleanly terminate application."""
        self._force_quit()
        event.accept()

    def _force_quit(self) -> None:
        """Terminate worker threads, hide tray, and exit application cleanly."""
        try:
            if self.tray_icon:
                self.tray_icon.hide()
            self.worker.stop_polling()
            self.thread.quit()
            self.thread.wait(1000)
        except Exception:
            pass
        QApplication.quit()
