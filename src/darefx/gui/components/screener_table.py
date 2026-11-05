"""Market Screener Table Component for DareFX Desktop Terminal."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from darefx.data.crypto_screener import CryptoScreener, ScreenerCandidate
from darefx.data.stock_screener import StockScreener
from darefx.gui.styles import ThemeColors, get_badge_style


class ScreenerTableWidget(QWidget):
    """Interactive real-time screener table for multi-asset scanning."""

    trade_requested = Signal(str, str)  # symbol, action ('BUY'/'SELL')

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.crypto_screener = CryptoScreener()
        self.stock_screener = StockScreener()
        self.candidates: list[ScreenerCandidate] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        title = QLabel("RADAR PASAR & SCREENER MULTI-ASET")
        title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {ThemeColors.TEXT_MUTED};")
        toolbar.addWidget(title)

        toolbar.addStretch()

        self.market_combo = QComboBox()
        self.market_combo.addItems(["🪙 Pasar Kripto (Top 50)", "🏛️ Saham Wall Street (S&P 500)"])
        self.market_combo.currentIndexChanged.connect(self._on_market_changed)
        toolbar.addWidget(self.market_combo)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Semua Sinyal", "Hanya BUY (+1)", "Hanya SELL (-1)"])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.filter_combo)

        self.scan_btn = QPushButton("🔄 Scan Pasar")
        self.scan_btn.setProperty("class", "primaryBtn")
        self.scan_btn.clicked.connect(self.run_scan)
        toolbar.addWidget(self.scan_btn)

        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Instrumen",
            "Harga Terakhir",
            "Perubahan 24h",
            "Volume 24h",
            "Regime Tren",
            "ADX (14)",
            "RSI (14)",
            "Sinyal AI",
            "Keyakinan",
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        self.status_label = QLabel("Siap memindai pasar.")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {ThemeColors.TEXT_MUTED};")
        layout.addWidget(self.status_label)

    def _on_market_changed(self) -> None:
        self.run_scan()

    def run_scan(self) -> None:
        """Execute market scanning sequence based on selected sector."""
        self.scan_btn.setEnabled(False)
        is_crypto = (self.market_combo.currentIndex() == 0)
        sector_name = "kripto" if is_crypto else "saham Wall Street"
        self.status_label.setText(f"Memindai aset likuid {sector_name}...")
        try:
            if is_crypto:
                symbols = self.crypto_screener.get_liquid_universe(min_volume_usd=5_000_000, top_n=20)
                self.candidates = self.crypto_screener.scan_universe(symbols, timeframe="4h")
            else:
                symbols = self.stock_screener.get_liquid_universe(top_n=20)
                self.candidates = self.stock_screener.scan_universe(symbols)

            self._render_table()
            now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            self.status_label.setText(f"Scan {sector_name} selesai pada {now_str}. Total aset: {len(self.candidates)}.")
        except Exception as err:
            self.status_label.setText(f"Scan gagal: {err}")
        finally:
            self.scan_btn.setEnabled(True)

    def _apply_filter(self) -> None:
        self._render_table()

    def _render_table(self) -> None:
        filter_idx = self.filter_combo.currentIndex()
        displayed = self.candidates

        if filter_idx == 1:
            displayed = [c for c in displayed if c.signal == "BUY"]
        elif filter_idx == 2:
            displayed = [c for c in displayed if c.signal == "SELL"]

        self.table.setRowCount(len(displayed))

        for row, cand in enumerate(displayed):
            # 0. Symbol
            sym_item = QTableWidgetItem(cand.symbol)
            sym_item.setFont(self.font())
            self.table.setItem(row, 0, sym_item)

            # 1. Price
            price_str = f"${cand.price:,.4f}" if cand.price < 10.0 else f"${cand.price:,.2f}"
            price_item = QTableWidgetItem(price_str)
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 1, price_item)

            # 2. 24h Change
            chg_str = f"{cand.change_24h_pct:+.2f}%"
            chg_item = QTableWidgetItem(chg_str)
            chg_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if cand.change_24h_pct > 0:
                chg_item.setForeground(Qt.GlobalColor.darkGreen)
            elif cand.change_24h_pct < 0:
                chg_item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 2, chg_item)

            # 3. 24h Volume
            vol_str = f"${cand.volume_24h_usd / 1_000_000:,.1f}M"
            vol_item = QTableWidgetItem(vol_str)
            vol_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, vol_item)

            # 4. Trend Bias
            trend_item = QTableWidgetItem(cand.trend_bias)
            self.table.setItem(row, 4, trend_item)

            # 5. ADX
            adx_item = QTableWidgetItem(f"{cand.adx_14:.1f}")
            adx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, adx_item)

            # 6. RSI
            rsi_item = QTableWidgetItem(f"{cand.rsi_14:.1f}")
            rsi_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, rsi_item)

            # 7. Sinyal Badge
            badge_widget = QWidget()
            b_layout = QHBoxLayout(badge_widget)
            b_layout.setContentsMargins(4, 2, 4, 2)
            badge_lbl = QLabel(cand.signal)
            badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge_lbl.setStyleSheet(get_badge_style(cand.signal))
            b_layout.addWidget(badge_lbl)
            self.table.setCellWidget(row, 7, badge_widget)

            # 8. Confidence
            conf_str = f"{cand.confidence * 100:.1f}%"
            conf_item = QTableWidgetItem(conf_str)
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 8, conf_item)
