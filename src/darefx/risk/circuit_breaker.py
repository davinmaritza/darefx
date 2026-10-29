"""Circuit Breaker State Machine for DareFX.

Enforces absolute capital preservation rules:
- ACTIVE: Normal trading permitted.
- PAUSED_DAILY: Triggered when daily loss reaches -5.0%. New trades halted until 00:00 UTC next day.
- SHUTDOWN: Triggered when total drawdown from equity peak exceeds -15.0%.
  All open positions terminated, trading loop shut down, requires manual CLI override.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Possible operating states for the risk circuit breaker."""

    ACTIVE = "ACTIVE"
    PAUSED_DAILY = "PAUSED_DAILY"
    SHUTDOWN = "SHUTDOWN"


@dataclass
class CircuitBreakerStatus:
    """Current state and diagnostic telemetry of the circuit breaker."""

    state: CircuitState
    current_equity: float
    peak_equity: float
    daily_open_equity: float
    peak_drawdown_pct: float
    daily_pnl_pct: float
    reason: str


class CircuitBreaker:
    """State machine enforcing institutional drawdown circuit breakers."""

    def __init__(
        self,
        max_daily_loss_pct: float = 5.0,
        max_total_drawdown_pct: float = 15.0,
        state_file: Path | str = "data/risk_state.json",
    ) -> None:
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_total_drawdown_pct = max_total_drawdown_pct
        self.state_file = Path(state_file)

        self.state: CircuitState = CircuitState.ACTIVE
        self.peak_equity: float = 10_000.0
        self.daily_open_equity: float = 10_000.0
        self.current_equity: float = 10_000.0
        self.last_trade_date: str = ""
        self.reason: str = "Initialized"

        self.load_state()

    def update(self, current_equity: float, current_date_str: str = "") -> CircuitBreakerStatus:
        """Update equity telemetry, evaluate drawdown thresholds, and trigger state transitions."""
        self.current_equity = current_equity

        # Handle daily date rollover (reset PAUSED_DAILY if new day starts)
        if current_date_str and current_date_str != self.last_trade_date:
            self.last_trade_date = current_date_str
            self.daily_open_equity = current_equity
            if self.state == CircuitState.PAUSED_DAILY:
                logger.info("New trading day detected (%s). Resetting circuit from PAUSED_DAILY to ACTIVE.", current_date_str)
                self.state = CircuitState.ACTIVE
                self.reason = "Daily reset"

        # Update high-water mark
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        # Calculate metrics
        peak_dd_pct = ((current_equity - self.peak_equity) / self.peak_equity) * 100.0
        daily_pnl_pct = ((current_equity - self.daily_open_equity) / self.daily_open_equity) * 100.0

        # Evaluate transitions
        if self.state != CircuitState.SHUTDOWN:
            # 1. Total Peak Drawdown Breach
            if abs(peak_dd_pct) >= self.max_total_drawdown_pct and peak_dd_pct < 0:
                self.state = CircuitState.SHUTDOWN
                self.reason = f"Maximum drawdown limit breached ({peak_dd_pct:.2f}% <= -{self.max_total_drawdown_pct:.1f}%)"
                logger.critical("CIRCUIT BREAKER TRIGGERED: %s", self.reason)

            # 2. Daily Loss Limit Breach
            elif abs(daily_pnl_pct) >= self.max_daily_loss_pct and daily_pnl_pct < 0 and self.state == CircuitState.ACTIVE:
                self.state = CircuitState.PAUSED_DAILY
                self.reason = f"Daily loss limit breached ({daily_pnl_pct:.2f}% <= -{self.max_daily_loss_pct:.1f}%)"
                logger.warning("CIRCUIT BREAKER TRIGGERED: %s", self.reason)

        self.save_state()

        return CircuitBreakerStatus(
            state=self.state,
            current_equity=self.current_equity,
            peak_equity=self.peak_equity,
            daily_open_equity=self.daily_open_equity,
            peak_drawdown_pct=abs(peak_dd_pct),
            daily_pnl_pct=daily_pnl_pct,
            reason=self.reason,
        )

    def can_open_new_trade(self) -> tuple[bool, str]:
        """Check if circuit breaker permits opening new positions."""
        if self.state == CircuitState.SHUTDOWN:
            return False, f"Trading halted: System in SHUTDOWN state ({self.reason})"
        if self.state == CircuitState.PAUSED_DAILY:
            return False, f"Trading halted: System in PAUSED_DAILY state ({self.reason})"
        return True, "Trading ACTIVE"

    def reset_shutdown(self) -> None:
        """Manual administrative reset to clear SHUTDOWN state."""
        logger.warning("Manual administrative override: Resetting SHUTDOWN to ACTIVE.")
        self.state = CircuitState.ACTIVE
        self.peak_equity = self.current_equity
        self.daily_open_equity = self.current_equity
        self.reason = "Manual administrative reset"
        self.save_state()

    def save_state(self) -> None:
        """Serialize state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "state": self.state.value,
                "current_equity": self.current_equity,
                "peak_equity": self.peak_equity,
                "daily_open_equity": self.daily_open_equity,
                "last_trade_date": self.last_trade_date,
                "reason": self.reason,
            }
            self.state_file.write_text(json.dumps(payload, indent=2))
        except Exception as err:
            logger.error("Failed to save circuit breaker state: %s", err)

    def load_state(self) -> None:
        """Load state from disk if exists."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self.state = CircuitState(data.get("state", "ACTIVE"))
                self.current_equity = float(data.get("current_equity", 10_000.0))
                self.peak_equity = float(data.get("peak_equity", 10_000.0))
                self.daily_open_equity = float(data.get("daily_open_equity", 10_000.0))
                self.last_trade_date = data.get("last_trade_date", "")
                self.reason = data.get("reason", "Loaded from disk")
            except Exception as err:
                logger.warning("Could not parse state file: %s. Using default.", err)
