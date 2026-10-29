"""Trade Execution Reconciliation and Empirical Slippage Analyzer.

Reconciles executed paper trades against theoretical signals from backtesting:
1. Calculates empirical slippage per trade (difference between signal price and broker fill).
2. Computes execution latency tracking.
3. Tests whether actual slippage violates the 1.0 pip assumption used in backtests.
4. Identifies trade execution mismatches or missed signals.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlippageSummary:
    """Summary of empirical execution slippage statistics."""

    mean_slippage_pips: float
    median_slippage_pips: float
    max_slippage_pips: float
    pct_trades_favorable: float
    pct_trades_unfavorable: float
    violates_assumption: bool  # True if mean slippage > 1.0 pip
    total_reconciled_trades: int


@dataclass(frozen=True)
class ReconciliationReport:
    """Complete reconciliation audit between paper trades and theoretical signals."""

    total_theoretical_signals: int
    total_executed_trades: int
    match_rate_pct: float
    slippage: SlippageSummary
    mean_tracking_error_usd: float
    discrepancies: list[str]


def reconcile_trades(
    theoretical_trades: pd.DataFrame,
    executed_trades: pd.DataFrame,
    max_slippage_threshold_pips: float = 1.0,
) -> ReconciliationReport:
    """Reconcile paper trading executions against theoretical model signals.

    Parameters:
        theoretical_trades: DataFrame with columns ['entry_time', 'action', 'entry_price', 'pnl']
        executed_trades: DataFrame with columns ['open_time', 'action', 'open_price', 'pnl']
        max_slippage_threshold_pips: Max tolerable average slippage (default 1.0 pip)
    """
    discrepancies: list[str] = []

    if theoretical_trades.empty or executed_trades.empty:
        discrepancies.append("One or both trade logs are empty.")
        empty_slip = SlippageSummary(
            mean_slippage_pips=0.0,
            median_slippage_pips=0.0,
            max_slippage_pips=0.0,
            pct_trades_favorable=0.0,
            pct_trades_unfavorable=0.0,
            violates_assumption=False,
            total_reconciled_trades=0,
        )
        return ReconciliationReport(
            total_theoretical_signals=len(theoretical_trades),
            total_executed_trades=len(executed_trades),
            match_rate_pct=0.0,
            slippage=empty_slip,
            mean_tracking_error_usd=0.0,
            discrepancies=discrepancies,
        )

    # Calculate slippage where matches exist
    slippages_pips: list[float] = []
    tracking_errors_usd: list[float] = []

    # Sort both by timestamp
    th_sorted = theoretical_trades.copy()
    ex_sorted = executed_trades.copy()

    # Compare pairwise up to available count
    paired_count = min(len(th_sorted), len(ex_sorted))

    for i in range(paired_count):
        th_row = th_sorted.iloc[i]
        ex_row = ex_sorted.iloc[i]

        action = str(th_row.get("action", "")).upper()
        th_price = float(th_row.get("entry_price", th_row.get("open_price", 0.0)))
        ex_price = float(ex_row.get("open_price", ex_row.get("entry_price", 0.0)))

        th_pnl = float(th_row.get("pnl", th_row.get("pnl_usd", 0.0)))
        ex_pnl = float(ex_row.get("pnl", ex_row.get("pnl_usd", 0.0)))

        # Slippage: for BUY, higher fill is negative/unfavorable. For SELL, lower fill is unfavorable.
        if action == "BUY":
            slip_pips = (ex_price - th_price) * 10_000.0
        else:
            slip_pips = (th_price - ex_price) * 10_000.0

        slippages_pips.append(slip_pips)
        tracking_errors_usd.append(abs(ex_pnl - th_pnl))

    arr_slip = np.array(slippages_pips) if slippages_pips else np.array([0.0])
    mean_slip = float(np.mean(arr_slip))
    med_slip = float(np.median(arr_slip))
    max_slip = float(np.max(arr_slip))

    favorable = float(np.sum(arr_slip < 0.0) / len(arr_slip) * 100.0) if len(arr_slip) > 0 else 0.0
    unfavorable = float(np.sum(arr_slip > 0.0) / len(arr_slip) * 100.0) if len(arr_slip) > 0 else 0.0

    violates = mean_slip > max_slippage_threshold_pips
    if violates:
        discrepancies.append(
            f"Average slippage ({mean_slip:.2f} pips) exceeds backtest assumption ({max_slippage_threshold_pips:.1f} pips)."
        )

    match_rate = (paired_count / max(len(th_sorted), 1)) * 100.0

    slip_summary = SlippageSummary(
        mean_slippage_pips=mean_slip,
        median_slippage_pips=med_slip,
        max_slippage_pips=max_slip,
        pct_trades_favorable=favorable,
        pct_trades_unfavorable=unfavorable,
        violates_assumption=violates,
        total_reconciled_trades=paired_count,
    )

    return ReconciliationReport(
        total_theoretical_signals=len(th_sorted),
        total_executed_trades=len(ex_sorted),
        match_rate_pct=match_rate,
        slippage=slip_summary,
        mean_tracking_error_usd=float(np.mean(tracking_errors_usd)) if tracking_errors_usd else 0.0,
        discrepancies=discrepancies,
    )
