"""Interactive Institutional Candlestick Chart Widget.

High-performance native PySide6 financial candlestick chart:
1. Candlestick rendering with wick, real body, and custom color themes
2. Overlaid indicators: EMA-20 (Sky Blue), EMA-50 (Amber), and Volume Histogram
3. Interactive mouse crosshair with dynamic price/time HUD coordinates
4. Smooth mouse drag panning and wheel zooming
5. Multi-asset support (Forex, Crypto CCXT, Equities/Alpaca)
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from darefx.gui.styles import ThemeColors

logger = logging.getLogger(__name__)


@dataclass
class CandleBar:
    """Single OHLCV candlestick bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    ema20: float | None = None
    ema50: float | None = None


class CandlestickCanvas(QWidget):
    """Native QPainter canvas rendering financial candlesticks and indicators."""

    bar_hovered = Signal(object)  # Emits hovered CandleBar or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(380)

        self.bars: list[CandleBar] = []
        self.visible_start: int = 0
        self.visible_count: int = 60

        # Visual configuration
        self.show_ema: bool = True
        self.show_volume: bool = True
        self.show_crosshair: bool = True

        # Mouse tracking
        self.mouse_pos: QPointF | None = None
        self.is_dragging: bool = False
        self.drag_start_x: float = 0.0
        self.drag_start_idx: int = 0

        # Palette
        self.bg_color = QColor("#0B0F19")
        self.grid_color = QColor("#1E293B")
        self.border_color = QColor("#334155")
        self.bull_color = QColor("#10B981")
        self.bear_color = QColor("#EF4444")
        self.ema20_color = QColor("#38BDF8")
        self.ema50_color = QColor("#F59E0B")
        self.text_color = QColor("#94A3B8")
        self.crosshair_color = QColor("#64748B")

    def set_bars(self, bars: list[CandleBar]) -> None:
        """Load new candle bars and reset visible window to latest bars."""
        self.bars = bars
        self.visible_count = min(60, max(20, len(bars)))
        self.visible_start = max(0, len(bars) - self.visible_count)
        self.update()

    def reset_view(self) -> None:
        """Reset zoom to show recent bars."""
        if self.bars:
            self.visible_count = min(60, len(self.bars))
            self.visible_start = max(0, len(self.bars) - self.visible_count)
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Handle zoom in / zoom out with mouse wheel."""
        if not self.bars:
            return
        delta = event.angleDelta().y()
        zoom_step = 4
        if delta > 0:
            new_count = max(15, self.visible_count - zoom_step)
        else:
            new_count = min(len(self.bars), self.visible_count + zoom_step)

        diff = self.visible_count - new_count
        self.visible_count = new_count
        max_start = len(self.bars) - self.visible_count
        self.visible_start = max(0, min(max_start, self.visible_start + diff // 2))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.drag_start_x = event.position().x()
            self.drag_start_idx = self.visible_start

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        self.mouse_pos = pos

        if self.is_dragging and self.bars:
            dx = pos.x() - self.drag_start_x
            chart_width = max(100.0, self.width() - 70.0)
            candle_width = chart_width / max(1, self.visible_count)
            bar_shift = int(dx / candle_width)
            max_start = len(self.bars) - self.visible_count
            self.visible_start = max(0, min(max_start, self.drag_start_idx - bar_shift))

        self.update()

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        self.mouse_pos = None
        self.bar_hovered.emit(None)
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # 1. Background
        painter.fillRect(0, 0, width, height, self.bg_color)
        painter.setPen(QPen(self.border_color, 1))
        painter.drawRect(0, 0, width - 1, height - 1)

        if not self.bars or self.visible_count <= 0:
            painter.setPen(self.text_color)
            painter.drawText(
                QRectF(0, 0, width, height),
                Qt.AlignmentFlag.AlignCenter,
                "Belum ada data grafik untuk aset ini",
            )
            return

        right_margin = 70.0
        bottom_margin = 25.0
        chart_w = max(50.0, width - right_margin)
        total_h = max(50.0, height - bottom_margin)

        vol_h = (total_h * 0.22) if self.show_volume else 0.0
        price_h = total_h - vol_h

        # Extract visible slice
        start = max(0, min(len(self.bars) - 1, self.visible_start))
        end = min(len(self.bars), start + self.visible_count)
        visible_bars = self.bars[start:end]

        if not visible_bars:
            return

        # Price Extents
        min_p = min(b.low for b in visible_bars)
        max_p = max(b.high for b in visible_bars)
        if self.show_ema:
            ema_vals = (
                [b.ema20 for b in visible_bars if b.ema20 is not None]
                + [b.ema50 for b in visible_bars if b.ema50 is not None]
            )
            if ema_vals:
                min_p = min(min_p, min(ema_vals))
                max_p = max(max_p, max(ema_vals))

        p_padding = (max_p - min_p) * 0.06 if max_p > min_p else 1.0
        min_p -= p_padding
        max_p += p_padding
        p_range = max(1e-6, max_p - min_p)

        max_vol = max((b.volume for b in visible_bars), default=1.0)
        max_vol = max(1.0, max_vol)

        candle_w = chart_w / len(visible_bars)
        body_w = max(2.0, candle_w * 0.72)

        def p_to_y(price: float) -> float:
            return 8.0 + (max_p - price) / p_range * (price_h - 16.0)

        def v_to_y(vol: float) -> float:
            return total_h - (vol / max_vol * (vol_h - 10.0))

        # 2. Draw Price Grid Lines
        painter.setFont(QFont("Segoe UI", 9))
        grid_pen = QPen(self.grid_color, 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)

        grid_steps = 5
        for i in range(grid_steps + 1):
            p_val = min_p + (p_range * (i / grid_steps))
            y_val = p_to_y(p_val)
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(0, y_val), QPointF(chart_w, y_val))

            painter.setPen(self.text_color)
            format_str = f"{p_val:.5f}" if p_val < 10 else f"{p_val:.2f}"
            lbl_rect = QRectF(chart_w + 5, y_val - 8, right_margin - 8, 16)
            painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignVCenter, format_str)

        # 3. Draw Volume Subplot Separator
        if self.show_volume:
            painter.setPen(QPen(self.border_color, 1))
            painter.drawLine(QPointF(0, price_h), QPointF(chart_w, price_h))

        # 4. Draw Candlesticks & Volume
        hovered_bar: CandleBar | None = None
        for i, bar in enumerate(visible_bars):
            cx = (i + 0.5) * candle_w
            is_bull = bar.close >= bar.open
            c_color = self.bull_color if is_bull else self.bear_color

            # Volume Bar
            if self.show_volume and bar.volume > 0:
                vy = v_to_y(bar.volume)
                vh = total_h - vy
                vol_color = QColor(c_color)
                vol_color.setAlpha(90)
                painter.fillRect(QRectF(cx - (body_w / 2), vy, body_w, vh), vol_color)

            # Wick
            painter.setPen(QPen(c_color, 1))
            y_high = p_to_y(bar.high)
            y_low = p_to_y(bar.low)
            painter.drawLine(QPointF(cx, y_high), QPointF(cx, y_low))

            # Candle Body
            y_open = p_to_y(bar.open)
            y_close = p_to_y(bar.close)
            y_top = min(y_open, y_close)
            y_body_h = max(2.0, abs(y_close - y_open))
            painter.fillRect(QRectF(cx - (body_w / 2), y_top, body_w, y_body_h), c_color)

            # Date labels
            if i % max(1, len(visible_bars) // 6) == 0:
                painter.setPen(self.text_color)
                d_str = bar.timestamp.strftime("%d %b")
                painter.drawText(
                    QRectF(cx - 30, total_h + 4, 60, 18),
                    Qt.AlignmentFlag.AlignCenter,
                    d_str,
                )

            # Check hover
            if self.mouse_pos and abs(self.mouse_pos.x() - cx) <= (candle_w / 2):
                hovered_bar = bar

        # 5. Draw EMA Lines
        if self.show_ema:
            pen20 = QPen(self.ema20_color, 1.6)
            pen50 = QPen(self.ema50_color, 1.6)

            p20_points: list[QPointF] = []
            for i, b in enumerate(visible_bars):
                if b.ema20 is not None:
                    p20_points.append(QPointF((i + 0.5) * candle_w, p_to_y(b.ema20)))
            if len(p20_points) > 1:
                painter.setPen(pen20)
                for k in range(len(p20_points) - 1):
                    painter.drawLine(p20_points[k], p20_points[k + 1])

            p50_points: list[QPointF] = []
            for i, b in enumerate(visible_bars):
                if b.ema50 is not None:
                    p50_points.append(QPointF((i + 0.5) * candle_w, p_to_y(b.ema50)))
            if len(p50_points) > 1:
                painter.setPen(pen50)
                for k in range(len(p50_points) - 1):
                    painter.drawLine(p50_points[k], p50_points[k + 1])

        # 6. Draw Crosshair
        is_hover_chart = (
            self.show_crosshair
            and self.mouse_pos
            and self.mouse_pos.x() < chart_w
            and self.mouse_pos.y() < total_h
        )
        if is_hover_chart:
            mx = self.mouse_pos.x()
            my = self.mouse_pos.y()
            ch_pen = QPen(self.crosshair_color, 1, Qt.PenStyle.DashLine)
            painter.setPen(ch_pen)
            painter.drawLine(QPointF(0, my), QPointF(chart_w, my))
            painter.drawLine(QPointF(mx, 0), QPointF(mx, total_h))

            # Crosshair price badge
            target_p = max_p - ((my - 8.0) / (price_h - 16.0)) * p_range
            p_text = f"{target_p:.5f}" if target_p < 10 else f"{target_p:.2f}"
            badge_rect = QRectF(chart_w + 2, my - 10, right_margin - 4, 20)
            painter.fillRect(badge_rect, QColor("#1E293B"))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, p_text)

        self.bar_hovered.emit(hovered_bar)


class CandlestickChartWidget(QWidget):
    """Complete Candlestick Chart component with symbol selector, HUD, and toggles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load_sample_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Top Control Toolbar
        toolbar = QFrame()
        tb_style = (
            f"background-color: {ThemeColors.BG_SURFACE}; "
            f"border: 1px solid {ThemeColors.BORDER_LIGHT}; "
            "border-radius: 6px; padding: 4px;"
        )
        toolbar.setStyleSheet(tb_style)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(10)

        tb_layout.addWidget(QLabel("Pasar:"))
        self.market_combo = QComboBox()
        self.market_combo.addItems(["Forex Currencies", "Crypto (CCXT)", "US Equities (Stocks)"])
        self.market_combo.currentIndexChanged.connect(self._on_market_changed)
        tb_layout.addWidget(self.market_combo)

        tb_layout.addWidget(QLabel("Simbol:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.setMinimumWidth(110)
        self.symbol_combo.currentIndexChanged.connect(self._on_symbol_changed)
        tb_layout.addWidget(self.symbol_combo)

        tb_layout.addWidget(QLabel("Timeframe:"))
        self.tf_combo = QComboBox()
        self.tf_combo.addItems(["D1 (Harian)", "H4 (4 Jam)", "H1 (1 Jam)"])
        tb_layout.addWidget(self.tf_combo)

        # Toggles
        self.chk_ema = QCheckBox("EMA 20/50")
        self.chk_ema.setChecked(True)
        self.chk_ema.toggled.connect(self._toggle_ema)
        tb_layout.addWidget(self.chk_ema)

        self.chk_vol = QCheckBox("Volume")
        self.chk_vol.setChecked(True)
        self.chk_vol.toggled.connect(self._toggle_volume)
        tb_layout.addWidget(self.chk_vol)

        tb_layout.addStretch()

        self.btn_reset = QPushButton("🔍 Fit All")
        self.btn_reset.clicked.connect(self._on_reset_view)
        tb_layout.addWidget(self.btn_reset)

        self.btn_refresh = QPushButton("🔄 Refresh Data")
        self.btn_refresh.clicked.connect(self.refresh_data)
        tb_layout.addWidget(self.btn_refresh)

        layout.addWidget(toolbar)

        # Live HUD Header Bar
        hud_frame = QFrame()
        hud_frame.setStyleSheet(
            "background-color: #0F172A; border-radius: 4px; padding: 6px 10px;"
        )
        hud_layout = QHBoxLayout(hud_frame)
        hud_layout.setContentsMargins(8, 2, 8, 2)
        hud_layout.setSpacing(16)

        self.lbl_hud_symbol = QLabel("EUR/USD D1")
        self.lbl_hud_symbol.setStyleSheet("font-weight: 800; color: #38BDF8; font-size: 13px;")
        hud_layout.addWidget(self.lbl_hud_symbol)

        self.lbl_hud_data = QLabel("O: --- | H: --- | L: --- | C: --- | Vol: --- | Chg: ---")
        self.lbl_hud_data.setStyleSheet("color: #94A3B8; font-family: monospace; font-size: 12px;")
        hud_layout.addWidget(self.lbl_hud_data)

        hud_layout.addStretch()

        self.lbl_hud_legend = QLabel("🔵 EMA 20  🟠 EMA 50")
        self.lbl_hud_legend.setStyleSheet("color: #CBD5E1; font-size: 11px;")
        hud_layout.addWidget(self.lbl_hud_legend)

        layout.addWidget(hud_frame)

        # Main Canvas
        self.canvas = CandlestickCanvas(self)
        self.canvas.bar_hovered.connect(self._on_bar_hovered)
        layout.addWidget(self.canvas, stretch=1)

        self._populate_symbols_for_market(0)

    def _on_market_changed(self, idx: int) -> None:
        self._populate_symbols_for_market(idx)
        self.refresh_data()

    def _populate_symbols_for_market(self, idx: int) -> None:
        self.symbol_combo.blockSignals(True)
        self.symbol_combo.clear()
        if idx == 0:  # Forex
            self.symbol_combo.addItems(["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"])
        elif idx == 1:  # Crypto
            self.symbol_combo.addItems(
                ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
            )
        else:  # Stocks
            self.symbol_combo.addItems(
                ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "META", "GOOGL"]
            )
        self.symbol_combo.blockSignals(False)

    def _on_symbol_changed(self) -> None:
        self.refresh_data()

    def _toggle_ema(self, checked: bool) -> None:
        self.canvas.show_ema = checked
        self.canvas.update()

    def _toggle_volume(self, checked: bool) -> None:
        self.canvas.show_volume = checked
        self.canvas.update()

    def _on_reset_view(self) -> None:
        self.canvas.reset_view()

    def _on_bar_hovered(self, bar: CandleBar | None) -> None:
        if bar is None:
            if self.canvas.bars:
                bar = self.canvas.bars[-1]
            else:
                return

        p_open = bar.open
        p_high = bar.high
        p_low = bar.low
        p_close = bar.close
        vol = bar.volume
        chg_pct = ((p_close - p_open) / p_open) * 100.0 if p_open > 0 else 0.0

        p_fmt = f"{p_close:.5f}" if p_close < 10 else f"{p_close:.2f}"
        o_fmt = f"{p_open:.5f}" if p_open < 10 else f"{p_open:.2f}"
        h_fmt = f"{p_high:.5f}" if p_high < 10 else f"{p_high:.2f}"
        l_fmt = f"{p_low:.5f}" if p_low < 10 else f"{p_low:.2f}"
        v_fmt = f"{vol:,.0f}"

        chg_color = "#10B981" if chg_pct >= 0 else "#EF4444"
        d_str = bar.timestamp.strftime("%Y-%m-%d")

        self.lbl_hud_symbol.setText(f"{self.symbol_combo.currentText()} ({d_str})")
        self.lbl_hud_data.setText(
            f"O: {o_fmt}  H: {h_fmt}  L: {l_fmt}  C: {p_fmt}  Vol: {v_fmt}  "
            f"<span style='color: {chg_color}; font-weight: bold;'>({chg_pct:+.2f}%)</span>"
        )

    def refresh_data(self) -> None:
        """Fetch fresh market bars or generate realistic technical fallback bars."""
        sym = self.symbol_combo.currentText()
        bars: list[CandleBar] = []

        try:
            from darefx.data.downloader import YahooFinanceDownloader
            yahoo_sym = sym
            if "/" in sym:
                yahoo_sym = sym.replace("/", "-")
            elif len(sym) == 6 and not any(c.isdigit() for c in sym):
                yahoo_sym = f"{sym}=X"

            dl = YahooFinanceDownloader(symbol=yahoo_sym)
            df = dl.fetch_daily_bars(range_str="6mo")
            if not df.empty:
                closes = df["close"].values
                ema20_vals = self._calc_ema(closes, 20)
                ema50_vals = self._calc_ema(closes, 50)

                for i, row in df.iterrows():
                    ts = row["timestamp"]
                    if hasattr(ts, "to_pydatetime"):
                        ts = ts.to_pydatetime()
                    bars.append(
                        CandleBar(
                            timestamp=ts,
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=float(row.get("volume", 0.0)),
                            ema20=ema20_vals[i],
                            ema50=ema50_vals[i],
                        )
                    )
        except Exception as err:
            logger.warning("Could not fetch online bars for %s: %s", sym, err)

        if not bars:
            bars = self._generate_synthetic_bars(sym)

        self.canvas.set_bars(bars)
        if bars:
            self._on_bar_hovered(bars[-1])

    def _calc_ema(self, series: Any, period: int) -> list[float | None]:
        res: list[float | None] = []
        multiplier = 2.0 / (period + 1.0)
        current_ema: float | None = None
        for i, val in enumerate(series):
            if i < period - 1:
                res.append(None)
            elif i == period - 1:
                current_ema = sum(series[:period]) / period
                res.append(current_ema)
            else:
                current_ema = (val - current_ema) * multiplier + current_ema  # type: ignore
                res.append(current_ema)
        return res

    def _generate_synthetic_bars(self, symbol: str) -> list[CandleBar]:
        """Generate realistic geometric Brownian motion candles for offline charting."""
        bars: list[CandleBar] = []
        if "BTC" in symbol:
            base_price = 68000.0
        elif "NVDA" in symbol:
            base_price = 138.0
        elif "EUR" in symbol:
            base_price = 1.0850
        else:
            base_price = 220.0
        price = base_price
        now = datetime.now(UTC) - timedelta(days=120)

        closes: list[float] = []
        raw_bars: list[dict[str, Any]] = []

        for day in range(120):
            dt = now + timedelta(days=day)
            drift = 0.0003
            volatility = 0.015 if "BTC" in symbol else 0.005 if "EUR" in symbol else 0.012
            ret = drift + volatility * random.gauss(0, 1)

            open_p = price
            close_p = open_p * (1.0 + ret)
            high_p = max(open_p, close_p) * (1.0 + abs(random.gauss(0, volatility * 0.5)))
            low_p = min(open_p, close_p) * (1.0 - abs(random.gauss(0, volatility * 0.5)))
            volume = random.uniform(50_000, 500_000)

            raw_bars.append({
                "timestamp": dt,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": volume,
            })
            closes.append(close_p)
            price = close_p

        ema20 = self._calc_ema(closes, 20)
        ema50 = self._calc_ema(closes, 50)

        for i, b in enumerate(raw_bars):
            bars.append(
                CandleBar(
                    timestamp=b["timestamp"],
                    open=b["open"],
                    high=b["high"],
                    low=b["low"],
                    close=b["close"],
                    volume=b["volume"],
                    ema20=ema20[i],
                    ema50=ema50[i],
                )
            )

        return bars

    def _load_sample_data(self) -> None:
        self.refresh_data()
