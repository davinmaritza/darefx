"""Order Executor for DareFX.

Applies pre-trade sanity checks (spread filter, circuit breaker, margin limit)
and coordinates with MT5Bridge to execute orders and protective exits.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from darefx.risk.circuit_breaker import CircuitBreaker
from darefx.risk.position_sizing import PositionSizingResult, calculate_fixed_fractional_lots
from darefx.trading.mt5_bridge import MT5Bridge, OrderResult, OrderType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionConfig:
    """Trade execution risk parameters."""

    max_spread_pips: float = 3.0
    risk_pct: float = 1.0
    leverage: float = 100.0
    magic_number: int = 20261029


@dataclass
class ExecutionReport:
    """Comprehensive post-execution report."""

    executed: bool
    status: str
    action: str = ""
    lots: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    ticket: int = 0
    message: str = ""


class OrderExecutor:
    """Executes trades against broker with safety and risk constraints."""

    def __init__(
        self,
        bridge: MT5Bridge,
        circuit_breaker: CircuitBreaker,
        config: ExecutionConfig = ExecutionConfig(),
    ) -> None:
        self.bridge = bridge
        self.circuit_breaker = circuit_breaker
        self.config = config

    def execute_signal(
        self,
        symbol: str,
        action: str,
        current_price: float,
        stop_loss: float,
        take_profit: float,
        current_spread_pips: float = 1.5,
    ) -> ExecutionReport:
        """Evaluate pre-trade constraints and submit protected market order."""
        # 1. Check Circuit Breaker
        allowed, reason = self.circuit_breaker.can_open_new_trade()
        if not allowed:
            logger.warning("Order rejected by Circuit Breaker: %s", reason)
            return ExecutionReport(
                executed=False,
                status="rejected_circuit_breaker",
                message=reason,
            )

        # 2. Check Spread Sanity
        if current_spread_pips > self.config.max_spread_pips:
            msg = f"Current spread ({current_spread_pips:.1f} pips) exceeds max tolerance ({self.config.max_spread_pips:.1f} pips)."
            logger.warning("Order rejected: %s", msg)
            return ExecutionReport(
                executed=False,
                status="rejected_high_spread",
                message=msg,
            )

        # 3. Retrieve Live Account Equity
        try:
            account = self.bridge.get_account_info()
            equity = account.equity
        except Exception as err:
            logger.error("Failed to query account balance from bridge: %s", err)
            equity = 10_000.0

        # 4. Calculate Position Sizing
        sizing: SizingResult = calculate_fixed_fractional_lots(
            account_equity=equity,
            entry_price=current_price,
            stop_loss_price=stop_loss,
            risk_pct=self.config.risk_pct,
            leverage=self.config.leverage,
        )

        if sizing.lots <= 0.0:
            msg = "Calculated position size is 0.0 lots (risk or margin limit exceeded)."
            logger.warning(msg)
            return ExecutionReport(
                executed=False,
                status="rejected_zero_size",
                message=msg,
            )

        # 5. Submit Order via MT5 Bridge
        res: OrderResult = self.bridge.send_market_order(
            symbol=symbol,
            action=action,
            volume=sizing.lots,
            sl=stop_loss,
            tp=take_profit,
            current_price=current_price,
            comment=f"darefx_{action.lower()}",
        )

        if not res.success:
            logger.error("Order submission failed: %s (Retcode: %d)", res.comment, res.retcode)
            return ExecutionReport(
                executed=False,
                status="execution_failed",
                action=action,
                lots=sizing.lots,
                message=f"Broker rejected: {res.comment}",
            )

        logger.info("Successfully executed %s %.2f lots on %s (Ticket #%d)",
                    action, sizing.lots, symbol, res.ticket)

        return ExecutionReport(
            executed=True,
            status="executed",
            action=action,
            lots=sizing.lots,
            entry_price=res.price if res.price > 0 else current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            ticket=res.ticket,
            message="Order filled successfully.",
        )
