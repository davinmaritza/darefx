"""Unified Multi-Asset Trading Scheduler and Execution Coordinator.

Orchestrates automated scanning, risk filtering, and execution across:
1. Forex (MT5) - Daily bar evaluation (22:05 UTC)
2. Crypto (CCXT) - 4-Hour periodic interval cycle
3. Stocks (Alpaca) - US Equities market session (09:35 - 15:55 EST)

All trade candidates are passed through the PortfolioGovernor to enforce
cross-market position limits, maximum capital risk, and duplicate prevention.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import schedule

from darefx.analysis.market_analyzer import MarketAnalyzer
from darefx.data.crypto_screener import CryptoScreener
from darefx.data.stock_screener import StockScreener
from darefx.notifications.telegram import TelegramNotifier
from darefx.risk.portfolio_governor import (
    AssetClass,
    PortfolioGovernor,
    SignalCandidate,
)
from darefx.trading.ccxt_adapter import CCXTAdapter
from darefx.trading.mt5_bridge import MT5Bridge, OrderType, Position
from darefx.trading.stock_adapter import StockAdapter

logger = logging.getLogger(__name__)


@dataclass
class MultiSchedulerConfig:
    """Multi-asset scheduler operational configuration."""
    forex_symbols: list[str] = field(default_factory=lambda: ["EURUSD", "GBPUSD", "USDJPY"])
    crypto_symbols: list[str] = field(
        default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    )
    stock_symbols: list[str] = field(
        default_factory=lambda: ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA"]
    )
    account_equity: float = 10_000.0

    execute_orders: bool = False
    forex_time_utc: str = "22:05"
    crypto_interval_hours: int = 4
    poll_interval_seconds: int = 5


class MultiScheduler:
    """Coordinating engine for cross-asset periodic evaluation and execution."""

    def __init__(
        self,
        config: MultiSchedulerConfig | None = None,
        mt5_bridge: MT5Bridge | None = None,
        ccxt_adapter: CCXTAdapter | None = None,
        stock_adapter: StockAdapter | None = None,
        governor: PortfolioGovernor | None = None,
        notifier: TelegramNotifier | None = None,
    ) -> None:
        self.config = config or MultiSchedulerConfig()
        self.mt5_bridge = mt5_bridge or MT5Bridge()
        self.ccxt_adapter = ccxt_adapter or CCXTAdapter()
        self.stock_adapter = stock_adapter or StockAdapter()
        self.governor = governor or PortfolioGovernor()
        self.notifier = notifier or TelegramNotifier()

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._listeners: list[Callable[[str, list[dict[str, Any]]], None]] = []

    def add_cycle_listener(self, callback: Callable[[str, list[dict[str, Any]]], None]) -> None:
        """Register a callback invoked when an asset cycle completes."""
        self._listeners.append(callback)

    def _notify_listeners(self, cycle_name: str, results: list[dict[str, Any]]) -> None:
        for cb in self._listeners:
            try:
                cb(cycle_name, results)
            except Exception as err:
                logger.error("Error in cycle listener: %s", err)

    def get_all_active_positions(self) -> list[Position]:
        """Aggregate open positions across all asset class adapters."""
        positions: list[Position] = []
        try:
            if not self.mt5_bridge.is_connected():
                self.mt5_bridge.connect()
            positions.extend(self.mt5_bridge.get_positions())
        except Exception as err:
            logger.debug("Could not fetch MT5 positions: %s", err)

        try:
            if not self.ccxt_adapter.is_connected():
                self.ccxt_adapter.connect()
            positions.extend(self.ccxt_adapter.get_positions())
        except Exception as err:
            logger.debug("Could not fetch CCXT positions: %s", err)

        try:
            if not self.stock_adapter.is_connected():
                self.stock_adapter.connect()
            positions.extend(self.stock_adapter.get_positions())
        except Exception as err:
            logger.debug("Could not fetch Stock positions: %s", err)

        return positions

    def evaluate_forex_candidates(self) -> list[SignalCandidate]:
        """Analyze forex pairs and generate trade candidates."""
        candidates: list[SignalCandidate] = []
        for sym in self.config.forex_symbols:
            try:
                analyzer = MarketAnalyzer(symbol=sym)
                report = analyzer.analyze(
                    account_equity=self.config.account_equity,
                    fetch_live=False,
                )
                if report.recommendation in ("BUY", "SELL"):
                    conf = report.prob_buy if report.recommendation == "BUY" else report.prob_sell
                    candidates.append(
                        SignalCandidate(
                            asset_class=AssetClass.FOREX,
                            symbol=sym,
                            action=report.recommendation,
                            entry_price=report.entry_price,
                            stop_loss=report.stop_loss,
                            take_profit=report.take_profit,
                            confidence=conf,
                            adx=report.adx_14,
                            atr=report.atr_pips,
                            risk_reward_ratio=report.risk_reward_ratio,
                            reasoning=report.reasoning,
                        )
                    )
            except Exception as err:
                logger.warning("Failed analyzing forex pair %s: %s", sym, err)
        return candidates

    def evaluate_crypto_candidates(self) -> list[SignalCandidate]:
        """Scan crypto pairs and generate trade candidates."""
        candidates: list[SignalCandidate] = []
        exchange_id = getattr(self.ccxt_adapter.credentials, "exchange_id", "binance")
        screener = CryptoScreener(exchange_id=exchange_id)
        for sym in self.config.crypto_symbols:
            try:
                item = screener.scan_symbol(sym)
                if item and item.signal in ("BUY", "SELL"):
                    price = getattr(item, "current_price", getattr(item, "price", 0.0))
                    adx_val = getattr(item, "adx_14", getattr(item, "adx", 25.0))
                    rsi_val = getattr(item, "rsi_14", getattr(item, "rsi", 50.0))
                    atr_val = getattr(item, "atr", price * 0.02)
                    atr_dist = atr_val if atr_val > 0 else (price * 0.02)
                    sl = (
                        price - (atr_dist * 1.5)
                        if item.signal == "BUY"
                        else price + (atr_dist * 1.5)
                    )
                    tp = (
                        price + (atr_dist * 2.0)
                        if item.signal == "BUY"
                        else price - (atr_dist * 2.0)
                    )
                    reason = f"Crypto technical setup: RSI={rsi_val:.1f}, ADX={adx_val:.1f}"
                    candidates.append(
                        SignalCandidate(
                            asset_class=AssetClass.CRYPTO,
                            symbol=sym,
                            action=item.signal,
                            entry_price=price,
                            stop_loss=sl,
                            take_profit=tp,
                            confidence=item.confidence,
                            adx=adx_val,
                            atr=atr_dist,
                            risk_reward_ratio=2.0 / 1.5,
                            reasoning=reason,
                        )
                    )
            except Exception as err:
                logger.warning("Failed scanning crypto symbol %s: %s", sym, err)
        return candidates

    def evaluate_stock_candidates(self) -> list[SignalCandidate]:
        """Scan US equities and generate trade candidates."""
        candidates: list[SignalCandidate] = []
        screener = StockScreener()
        for sym in self.config.stock_symbols:
            try:
                item = screener.scan_symbol(sym)
                if item and item.signal in ("BUY", "SELL"):
                    price = getattr(item, "current_price", getattr(item, "price", 0.0))
                    adx_val = getattr(item, "adx_14", getattr(item, "adx", 25.0))
                    rsi_val = getattr(item, "rsi_14", getattr(item, "rsi", 50.0))
                    atr_val = getattr(item, "atr", price * 0.015)
                    atr_dist = atr_val if atr_val > 0 else (price * 0.015)
                    sl = (
                        price - (atr_dist * 1.5)
                        if item.signal == "BUY"
                        else price + (atr_dist * 1.5)
                    )
                    tp = (
                        price + (atr_dist * 2.0)
                        if item.signal == "BUY"
                        else price - (atr_dist * 2.0)
                    )
                    change_val = getattr(item, "change_pct", getattr(item, "change_24h_pct", 0.0))
                    reason = (
                        f"Stock breakout setup: RSI={rsi_val:.1f}, "
                        f"Change={change_val:+.2f}%"
                    )
                    candidates.append(
                        SignalCandidate(
                            asset_class=AssetClass.STOCKS,
                            symbol=sym,
                            action=item.signal,
                            entry_price=price,
                            stop_loss=sl,
                            take_profit=tp,
                            confidence=item.confidence,
                            adx=adx_val,
                            atr=atr_dist,
                            risk_reward_ratio=2.0 / 1.5,
                            reasoning=reason,
                        )
                    )
            except Exception as err:
                logger.warning("Failed scanning stock symbol %s: %s", sym, err)
        return candidates



    def execute_candidate(self, cand: SignalCandidate) -> dict[str, Any]:
        """Dispatch a signal candidate to its corresponding asset adapter."""
        action = cand.action
        order_type = OrderType.BUY if action == "BUY" else OrderType.SELL
        result: dict[str, Any] = {
            "symbol": cand.symbol,
            "asset_class": cand.asset_class.value,
            "action": action,
            "entry_price": cand.entry_price,
            "stop_loss": cand.stop_loss,
            "take_profit": cand.take_profit,
            "confidence": cand.confidence,
            "ticket": 0,
            "status": "simulated",
            "message": "Paper execution simulation",
        }

        if not self.config.execute_orders:
            conf_pct = cand.confidence * 100
            logger.info(
                "[SIMULATION] Signal: %s %s @ %.4f (SL: %.4f, TP: %.4f, Conf: %.1f%%)",
                action, cand.symbol, cand.entry_price, cand.stop_loss, cand.take_profit, conf_pct,
            )
            return result

        try:
            if cand.asset_class == AssetClass.FOREX:
                self.mt5_bridge.connect()
                # 0.01 lot minimum test sizing
                res = self.mt5_bridge.send_market_order(
                    symbol=cand.symbol,
                    order_type=order_type,
                    volume=0.01,
                    sl=cand.stop_loss,
                    tp=cand.take_profit,
                    comment="DareFX Forex Multi-Scheduler",
                )
            elif cand.asset_class == AssetClass.CRYPTO:
                self.ccxt_adapter.connect()
                # Calculate small sizing
                res = self.ccxt_adapter.send_market_order(
                    symbol=cand.symbol,
                    order_type=order_type,
                    volume=0.001 if "BTC" in cand.symbol else 0.01,
                    sl=cand.stop_loss,
                    tp=cand.take_profit,
                    comment="DareFX Crypto Multi-Scheduler",
                )
            else:  # STOCKS
                self.stock_adapter.connect()
                res = self.stock_adapter.send_market_order(
                    symbol=cand.symbol,
                    order_type=order_type,
                    volume=1.0,
                    sl=cand.stop_loss,
                    tp=cand.take_profit,
                    comment="DareFX Equities Multi-Scheduler",
                )

            result["ticket"] = res.ticket
            result["status"] = "executed" if res.success else "failed"
            order_msg = "Order placed successfully" if res.success else f"Code: {res.retcode}"
            result["message"] = order_msg


            if res.success:
                self.notifier.notify_trade_opened(
                    direction=action,
                    symbol=cand.symbol,
                    lots=res.volume,
                    entry_price=res.price or cand.entry_price,
                    stop_loss=cand.stop_loss,
                    take_profit=cand.take_profit,
                    confidence=cand.confidence,
                )
        except Exception as err:
            logger.error("Execution failed for %s: %s", cand.symbol, err)
            result["status"] = "error"
            result["message"] = str(err)

        return result

    def run_all_cycles(self) -> dict[str, list[dict[str, Any]]]:
        """Execute a full multi-asset scan, filter with PortfolioGovernor, and dispatch."""
        logger.info("Executing unified multi-asset cycle across Forex, Crypto, and Stocks...")
        current_positions = self.get_all_active_positions()

        # 1. Harvest candidates from all asset classes
        all_candidates: list[SignalCandidate] = []
        all_candidates.extend(self.evaluate_forex_candidates())
        all_candidates.extend(self.evaluate_crypto_candidates())
        all_candidates.extend(self.evaluate_stock_candidates())

        logger.info("Discovered %d raw signal candidates across markets.", len(all_candidates))

        # 2. Filter and rank using Portfolio Governor
        approved = self.governor.rank_and_filter(
            candidates=all_candidates,
            current_positions=current_positions,
            current_equity=self.config.account_equity,
        )
        logger.info("Approved %d candidates within risk limits.", len(approved))

        # 3. Execute approved signals
        dispatched: dict[str, list[dict[str, Any]]] = {
            "forex": [],
            "crypto": [],
            "stocks": [],
        }

        for cand in approved:
            res = self.execute_candidate(cand)
            dispatched[cand.asset_class.value].append(res)

        self._notify_listeners("all", [r for items in dispatched.values() for r in items])
        return dispatched

    def start(self) -> None:
        """Start the background multi-asset schedule worker."""
        if self._thread and self._thread.is_alive():
            logger.warning("MultiScheduler already running.")
            return

        self._stop_event.clear()

        # Set up schedule jobs
        schedule.clear("darefx_multi")
        schedule.every().day.at(self.config.forex_time_utc).do(self.run_all_cycles).tag("darefx_multi")
        schedule.every(self.config.crypto_interval_hours).hours.do(self.run_all_cycles).tag("darefx_multi")

        def _worker_loop() -> None:
            logger.info("MultiScheduler background worker started.")
            while not self._stop_event.is_set():
                schedule.run_pending()
                time.sleep(self.config.poll_interval_seconds)
            logger.info("MultiScheduler background worker stopped.")

        self._thread = threading.Thread(
            target=_worker_loop,
            daemon=True,
            name="MultiSchedulerWorker",
        )
        self._thread.start()


    def stop(self) -> None:
        """Stop the background scheduler."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            self._thread = None
        schedule.clear("darefx_multi")

    @property
    def is_running(self) -> bool:
        """Check if scheduler worker is active."""
        return self._thread is not None and self._thread.is_alive()
