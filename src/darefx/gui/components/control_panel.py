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
