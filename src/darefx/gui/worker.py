"""Background worker thread and controller for MT5 trading engine."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from darefx.analysis.market_analyzer import MarketAnalysisReport, MarketAnalyzer
from darefx.risk.circuit_breaker import CircuitBreaker
from darefx.trading.mt5_bridge import AccountInfo, MT5Bridge, MT5Credentials, Position

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
        if bridge is not None:
            self.bridge = bridge
        else:
            self.bridge = MT5Bridge(credentials=MT5Credentials(simulation_mode=simulation))
        self.circuit_breaker = CircuitBreaker()
        self.autotrade_enabled = True
        self._poll_timer: QTimer | None = None

    @property
    def is_simulation(self) -> bool:
        return self.bridge.credentials.simulation_mode

    def start_polling(self) -> None:
        """Start the periodic polling timer for account & active positions."""
        self.bridge.connect()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self.poll_account_and_positions)
        self._poll_timer.start(self.poll_interval_ms)
        self.log_emitted.emit(f"Engine worker started (Simulation={self.is_simulation})", "INFO")
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
            if not self.bridge.is_connected:
                self.bridge.connect()
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
