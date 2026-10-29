"""Risk management position sizing module for DareFX.

Implements:
1. Fixed fractional position sizing (default 1.0% risk per trade).
2. Half-Kelly sizing with conservative safety ceiling.
3. Margin utilization limits and standard lot quantization (0.01 micro-lot step).
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math

logger = logging.getLogger(__name__)

# Institutional Forex Constants
STANDARD_LOT_UNITS = 100_000.0  # 1 standard lot = 100,000 units of base currency
MICRO_LOT_UNITS = 1_000.0        # 1 micro lot = 1,000 units (0.01 lot)
PIP_SIZE = 0.0001                # 1 pip for 4/5-decimal pairs like EUR/USD
PIP_VALUE_STANDARD_LOT = 10.0    # 1 pip move in 1.0 standard lot EUR/USD = $10.00 USD


@dataclass(frozen=True)
class PositionSizingResult:
    """Calculated position sizing parameters."""

    lots: float
    units: float
    risk_amount_usd: float
    margin_required_usd: float
    margin_utilization_pct: float
    stop_distance_pips: float


def calculate_fixed_fractional_lots(
    account_equity: float,
    entry_price: float,
    stop_loss_price: float,
    risk_pct: float = 1.0,
    max_margin_pct: float = 5.0,
    leverage: float = 100.0,
) -> PositionSizingResult:
    """Calculate exact order volume in standard lots using fixed fractional risk.

    Formula:
        Lots = (Account Equity * Risk %) / (Stop Loss Distance in Pips * Pip Value per Lot)

    Parameters:
        account_equity: Current portfolio equity in USD
        entry_price: Planned entry price
        stop_loss_price: Planned protective stop loss price
        risk_pct: Percentage of account equity risked (default 1.0%)
        max_margin_pct: Maximum allowed margin utilization (default 5.0%)
        leverage: Broker account leverage (default 1:100)

    Returns:
        PositionSizingResult with lot size, units, and risk metrics
    """
    if account_equity <= 0:
        raise ValueError("Account equity must be positive.")

    price_diff = abs(entry_price - stop_loss_price)
    if price_diff <= 0:
        raise ValueError("Stop loss price cannot equal entry price.")

    stop_pips = price_diff / PIP_SIZE
    risk_usd = account_equity * (risk_pct / 100.0)

    # Lots = Risk ($) / (Stop Pips * $10 per pip per lot)
    raw_lots = risk_usd / (stop_pips * PIP_VALUE_STANDARD_LOT)

    # Margin check: Required margin = (Lots * 100,000 * Entry Price) / Leverage
    max_margin_usd = account_equity * (max_margin_pct / 100.0)
    max_lots_by_margin = (max_margin_usd * leverage) / (STANDARD_LOT_UNITS * entry_price)

    # Restrict to margin limit
    effective_lots = min(raw_lots, max_lots_by_margin)

    # Quantize to 0.01 micro lot step, rounded down for conservative safety
    quantized_lots = math.floor(effective_lots * 100.0) / 100.0

    # Minimum order volume is 0.01 lot
    if quantized_lots < 0.01:
        quantized_lots = 0.01

    units = quantized_lots * STANDARD_LOT_UNITS
    actual_risk_usd = quantized_lots * stop_pips * PIP_VALUE_STANDARD_LOT
    margin_required = (units * entry_price) / leverage
    margin_utilization = (margin_required / account_equity) * 100.0

    return PositionSizingResult(
        lots=quantized_lots,
        units=units,
        risk_amount_usd=actual_risk_usd,
        margin_required_usd=margin_required,
        margin_utilization_pct=margin_utilization,
        stop_distance_pips=stop_pips,
    )


def calculate_half_kelly_fraction(
    win_rate: float,
    win_loss_ratio: float,
    max_risk_cap_pct: float = 2.0,
) -> float:
    """Calculate conservative Half-Kelly optimal risk percentage.

    Formula:
        f* = (p * b - q) / b
        Half-Kelly = 0.5 * f*

    Parameters:
        win_rate: Empirical probability of win (e.g. 0.57)
        win_loss_ratio: Ratio of average win to average loss (b)
        max_risk_cap_pct: Hard ceiling cap (default 2.0%)

    Returns:
        Safe fractional risk percentage
    """
    if win_loss_ratio <= 0:
        return 0.0

    p = win_rate
    q = 1.0 - p
    b = win_loss_ratio

    full_kelly = (p * b - q) / b
    if full_kelly <= 0:
        return 0.0  # Zero edge -> zero risk

    half_kelly_pct = (full_kelly * 0.5) * 100.0
    return min(half_kelly_pct, max_risk_cap_pct)
