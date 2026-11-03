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
            item_profit.setForeground(Qt.GlobalColor.darkGreen if pos.profit >= 0 else Qt.GlobalColor.darkRed)
            item_profit.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(row, 8, item_profit)

            # Pips
            if hasattr(pos, "pips"):
                pips_val = pos.pips
            else:
                pip_size = 0.0001 if "JPY" not in pos.symbol else 0.01
                if str(pos.order_type).upper().endswith("BUY"):
                    pips_val = (pos.current_price - pos.open_price) / pip_size
                else:
                    pips_val = (pos.open_price - pos.current_price) / pip_size
            item_pips = QTableWidgetItem(f"{pips_val:+.1f} pips")
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
