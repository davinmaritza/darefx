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
