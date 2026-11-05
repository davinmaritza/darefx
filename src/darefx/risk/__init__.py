"""Risk management subpackage for DareFX."""

from darefx.risk.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerStatus
from darefx.risk.position_sizing import (
    PositionSizingResult,
    calculate_fixed_fractional_lots,
    calculate_half_kelly_fraction,
)
from darefx.risk.news_filter import EconomicNewsFilter, EconomicEvent
from darefx.risk.portfolio_governor import (
    AssetClass,
    PortfolioGovernor,
    PortfolioGovernorConfig,
    SignalCandidate,
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerStatus",
    "PositionSizingResult",
    "calculate_fixed_fractional_lots",
    "calculate_half_kelly_fraction",
    "EconomicNewsFilter",
    "EconomicEvent",
    "AssetClass",
    "PortfolioGovernor",
    "PortfolioGovernorConfig",
    "SignalCandidate",
]

