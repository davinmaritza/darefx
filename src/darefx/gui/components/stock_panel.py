"""Equities and Stock Portfolio Cockpit Component for DareFX Desktop Terminal."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from darefx.gui.components.metric_card import MetricCard
from darefx.gui.styles import ThemeColors, get_badge_style
from darefx.trading.mt5_bridge import OrderType, Position
from darefx.trading.stock_adapter import StockAdapter

logger = logging.getLogger(__name__)


class StockPanelWidget(QWidget):
    """Dedicated interactive dashboard for US Equities and Stocks (Alpaca)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.adapter = StockAdapter()
        self._build_ui()
        self.refresh_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 1. Financial Metrics Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        self.card_cash = MetricCard("Saldo Kas Saham", "$0.00", "Settled Cash")
        self.card_equity = MetricCard("Nilai Portofolio", "$0.00", "Total Equities")
        self.card_holdings = MetricCard("Saham Dimiliki", "0 Emiten", "Daya Beli 4:1")
        self.card_status = MetricCard("Bursa Wall Street", "ALPACA-SIM", "S&P 500 / NASDAQ", is_positive=True)

        metrics_layout.addWidget(self.card_cash)
        metrics_layout.addWidget(self.card_equity)
        metrics_layout.addWidget(self.card_holdings)
        metrics_layout.addWidget(self.card_status)
        layout.addLayout(metrics_layout)

        # 2. Control Toolbar
        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet(
            f"background-color: {ThemeColors.BG_SURFACE}; border: 1px solid {ThemeColors.BORDER_LIGHT}; border-radius: 8px; padding: 6px;"
        )
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(10, 6, 10, 6)
        toolbar_layout.setSpacing(10)

        toolbar_layout.addWidget(QLabel("Ticker Saham:"))
        self.sym_combo = QComboBox()
        self.sym_combo.addItems(["NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "META", "GOOGL", "AMD"])
        toolbar_layout.addWidget(self.sym_combo)

        toolbar_layout.addWidget(QLabel("Lembar Saham:"))
        self.shares_spin = QDoubleSpinBox()
        self.shares_spin.setRange(1.0, 100_000.0)
        self.shares_spin.setSingleStep(5.0)
        self.shares_spin.setValue(10.0)
        toolbar_layout.addWidget(self.shares_spin)

        self.buy_btn = QPushButton("⚡ Beli Saham (Long)")
        self.buy_btn.setProperty("class", "successBtn")
        self.buy_btn.clicked.connect(lambda: self._place_order(OrderType.BUY))
        toolbar_layout.addWidget(self.buy_btn)

        self.sell_btn = QPushButton("⚡ Jual Saham (Short)")
        self.sell_btn.setProperty("class", "dangerBtn")
        self.sell_btn.clicked.connect(lambda: self._place_order(OrderType.SELL))
        toolbar_layout.addWidget(self.sell_btn)

        toolbar_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_state)
        toolbar_layout.addWidget(self.refresh_btn)

        self.panic_btn = QPushButton("🚨 Tutup Semua Saham")
        self.panic_btn.setProperty("class", "dangerBtn")
        self.panic_btn.clicked.connect(self._panic_close_all)
        toolbar_layout.addWidget(self.panic_btn)

        layout.addWidget(toolbar_frame)

        # 3. Active Holdings Table
        table_header = QLabel("PORTOFOLIO SAHAM AKTIF & POSISI TERBUKA (US EQUITIES)")
        table_header.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_MUTED};")
        layout.addWidget(table_header)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Tiket ID",
            "Ticker Saham",
            "Posisi",
            "Jumlah Lembar",
            "Harga Rata-Rata",
            "Harga Pasar",
            "Unrealized PnL ($)",
            "Aksi",
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def refresh_state(self) -> None:
        """Fetch updated cash and stock holdings."""
        try:
            acc = self.adapter.get_account_info()
            positions = self.adapter.get_positions()

            self.card_cash.update_values(f"${acc.balance:,.2f}", f"Daya Beli: ${acc.free_margin:,.2f}")
            self.card_equity.update_values(f"${acc.equity:,.2f}", "Portofolio Aktif")
            self.card_holdings.update_values(f"{len(positions)} Emiten", f"Margin: ${acc.margin:,.2f}")
            self.card_status.update_values(acc.server, "Online", is_positive=True)

            self._render_positions(positions)
        except Exception as err:
            logger.error("Failed to refresh stock panel: %s", err)

    def _render_positions(self, positions: list[Position]) -> None:
        self.table.setRowCount(len(positions))

        for row, pos in enumerate(positions):
            # 0. Ticket
            self.table.setItem(row, 0, QTableWidgetItem(f"#{pos.ticket}"))

            # 1. Symbol
            self.table.setItem(row, 1, QTableWidgetItem(pos.symbol))

            # 2. Side
            badge_widget = QWidget()
            b_layout = QHBoxLayout(badge_widget)
            b_layout.setContentsMargins(4, 2, 4, 2)
            lbl = QLabel(pos.order_type.value)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(get_badge_style(pos.order_type.value.lower()))
            b_layout.addWidget(lbl)
            self.table.setCellWidget(row, 2, badge_widget)

            # 3. Shares
            self.table.setItem(row, 3, QTableWidgetItem(f"{pos.volume:,.2f} shs"))

            # 4. Entry Price
            self.table.setItem(row, 4, QTableWidgetItem(f"${pos.open_price:,.2f}"))

            # 5. Current Price
            self.table.setItem(row, 5, QTableWidgetItem(f"${pos.current_price:,.2f}"))

            # 6. PnL
            pnl_item = QTableWidgetItem(f"${pos.profit:+,.2f}")
            if pos.profit > 0:
                pnl_item.setForeground(Qt.GlobalColor.darkGreen)
            elif pos.profit < 0:
                pnl_item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 6, pnl_item)

            # 7. Action
            close_btn = QPushButton("Liquidate")
            close_btn.setProperty("class", "dangerBtn")
            close_btn.clicked.connect(lambda checked=False, t=pos.ticket: self._close_order(t))
            self.table.setCellWidget(row, 7, close_btn)

    def _place_order(self, order_type: OrderType) -> None:
        sym = self.sym_combo.currentText()
        shares = self.shares_spin.value()
        res = self.adapter.send_market_order(symbol=sym, order_type=order_type, volume=shares)
        if res.success:
            self.refresh_state()
        else:
            QMessageBox.warning(self, "Order Saham Gagal", f"Gagal mengeksekusi order {sym}: {res.comment}")

    def _close_order(self, ticket: int) -> None:
        if self.adapter.close_position(ticket):
            self.refresh_state()
        else:
            QMessageBox.warning(self, "Tutup Saham Gagal", f"Gagal menutup posisi #{ticket}.")

    def _panic_close_all(self) -> None:
        positions = self.adapter.get_positions()
        if not positions:
            return

        confirm = QMessageBox.question(
            self,
            "Konfirmasi Likuidasi Portofolio Saham",
            f"Apakah Anda yakin ingin menjual/menutup SEMUA ({len(positions)}) posisi saham terbuka?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            for p in positions:
                self.adapter.close_position(p.ticket)
            self.refresh_state()
