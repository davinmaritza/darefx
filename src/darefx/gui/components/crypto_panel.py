"""Crypto Portfolio and Execution Cockpit Component for DareFX Desktop Terminal."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from darefx.gui.components.metric_card import MetricCard
from darefx.gui.styles import ThemeColors, get_badge_style
from darefx.trading.ccxt_adapter import CCXTAdapter
from darefx.trading.mt5_bridge import OrderResult, OrderType, Position

logger = logging.getLogger(__name__)


class CryptoPanelWidget(QWidget):
    """Dedicated interactive dashboard for Crypto CCXT exchange execution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.adapter = CCXTAdapter()
        self._build_ui()
        self.refresh_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 1. Top Metrics Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        self.card_balance = MetricCard("Saldo USDT", "$0.00", "Exchange Wallet")
        self.card_equity = MetricCard("Ekuitas USDT", "$0.00", "Floating PnL")
        self.card_positions = MetricCard("Posisi Kripto", "0 Kontrak", "Margin Terpakai")
        self.card_status = MetricCard("Status Exchange", "SIMULATION", "CCXT Driver", is_positive=True)

        metrics_layout.addWidget(self.card_balance)
        metrics_layout.addWidget(self.card_equity)
        metrics_layout.addWidget(self.card_positions)
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

        toolbar_layout.addWidget(QLabel("Instrumen:"))
        self.sym_combo = QComboBox()
        self.sym_combo.addItems(["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT", "AVAX/USDT", "SUI/USDT"])
        toolbar_layout.addWidget(self.sym_combo)

        toolbar_layout.addWidget(QLabel("Jumlah/Kontrak:"))
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.001, 1000.0)
        self.amount_spin.setSingleStep(0.01)
        self.amount_spin.setValue(0.10)
        toolbar_layout.addWidget(self.amount_spin)

        self.buy_btn = QPushButton("⚡ Beli (Long)")
        self.buy_btn.setProperty("class", "successBtn")
        self.buy_btn.clicked.connect(lambda: self._place_order(OrderType.BUY))
        toolbar_layout.addWidget(self.buy_btn)

        self.sell_btn = QPushButton("⚡ Jual (Short)")
        self.sell_btn.setProperty("class", "dangerBtn")
        self.sell_btn.clicked.connect(lambda: self._place_order(OrderType.SELL))
        toolbar_layout.addWidget(self.sell_btn)

        toolbar_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_state)
        toolbar_layout.addWidget(self.refresh_btn)

        self.panic_btn = QPushButton("🚨 Tutup Semua Kripto")
        self.panic_btn.setProperty("class", "dangerBtn")
        self.panic_btn.clicked.connect(self._panic_close_all)
        toolbar_layout.addWidget(self.panic_btn)

        layout.addWidget(toolbar_frame)

        # 3. Active Positions Table
        table_header = QLabel("POSISI AKTIF DERIVATIF & SPOT KRIPTO")
        table_header.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_MUTED};")
        layout.addWidget(table_header)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Tiket ID",
            "Pasangan Koin",
            "Arah",
            "Jumlah Kontrak",
            "Harga Masuk",
            "Harga Saat Ini",
            "Floating PnL (USDT)",
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
        """Fetch updated balances and positions from CCXT."""
        try:
            acc = self.adapter.get_account_info()
            positions = self.adapter.get_positions()

            self.card_balance.update_values(f"${acc.balance:,.2f}", f"Bebas: ${acc.free_margin:,.2f}")
            float_pnl = sum(p.profit for p in positions)
            self.card_equity.update_values(f"${acc.equity:,.2f}", f"Floating: {float_pnl:+,.2f}")
            self.card_positions.update_values(f"{len(positions)} Posisi", f"Margin: ${acc.margin:,.2f}")
            self.card_status.update_values(acc.server, "Online", is_positive=True)

            self._render_positions(positions)
        except Exception as err:
            logger.error("Failed to refresh crypto panel: %s", err)

    def _render_positions(self, positions: list[Position]) -> None:
        self.table.setRowCount(len(positions))

        for row, pos in enumerate(positions):
            # 0. Ticket
            self.table.setItem(row, 0, QTableWidgetItem(f"#{pos.ticket}"))

            # 1. Symbol
            self.table.setItem(row, 1, QTableWidgetItem(pos.symbol))

            # 2. Side Badge
            badge_widget = QWidget()
            b_layout = QHBoxLayout(badge_widget)
            b_layout.setContentsMargins(4, 2, 4, 2)
            lbl = QLabel(pos.order_type.value)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(get_badge_style(pos.order_type.value.lower()))
            b_layout.addWidget(lbl)
            self.table.setCellWidget(row, 2, badge_widget)

            # 3. Volume
            self.table.setItem(row, 3, QTableWidgetItem(f"{pos.volume:.4f}"))

            # 4. Open price
            self.table.setItem(row, 4, QTableWidgetItem(f"${pos.open_price:,.2f}"))

            # 5. Current price
            self.table.setItem(row, 5, QTableWidgetItem(f"${pos.current_price:,.2f}"))

            # 6. PnL
            pnl_item = QTableWidgetItem(f"${pos.profit:+,.2f} USDT")
            if pos.profit > 0:
                pnl_item.setForeground(Qt.GlobalColor.darkGreen)
            elif pos.profit < 0:
                pnl_item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 6, pnl_item)

            # 7. Action Close button
            close_btn = QPushButton("Tutup")
            close_btn.setProperty("class", "dangerBtn")
            close_btn.clicked.connect(lambda checked=False, t=pos.ticket: self._close_order(t))
            self.table.setCellWidget(row, 7, close_btn)

    def _place_order(self, order_type: OrderType) -> None:
        sym = self.sym_combo.currentText()
        amount = self.amount_spin.value()
        res = self.adapter.send_market_order(symbol=sym, order_type=order_type, volume=amount)
        if res.success:
            self.refresh_state()
        else:
            QMessageBox.warning(self, "Order Gagal", f"Gagal mengeksekusi order {sym}: {res.comment}")

    def _close_order(self, ticket: int) -> None:
        if self.adapter.close_position(ticket):
            self.refresh_state()
        else:
            QMessageBox.warning(self, "Tutup Gagal", f"Gagal menutup posisi #{ticket}.")

    def _panic_close_all(self) -> None:
        positions = self.adapter.get_positions()
        if not positions:
            return

        confirm = QMessageBox.question(
            self,
            "Konfirmasi Tutup Darurat",
            f"Apakah Anda yakin ingin melikuidasi SEMUA ({len(positions)}) posisi kripto terbuka seketika?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            for p in positions:
                self.adapter.close_position(p.ticket)
            self.refresh_state()
