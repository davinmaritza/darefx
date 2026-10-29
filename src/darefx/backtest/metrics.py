"""Quantitative financial performance metrics for DareFX."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerformanceMetrics:
    """Comprehensive performance metrics summary."""

    initial_balance: float
    final_balance: float
    total_return_pct: float
    cagr_pct: float
    annualized_volatility_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_duration_days: int
    win_rate_pct: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_pnl_usd: float
    avg_win_usd: float
    avg_loss_usd: float
    win_loss_ratio: float
    expectancy_usd: float


def calculate_metrics(
    equity_series: pd.Series,
    trade_pnls: list[float],
    annualization_factor: int = 252,
) -> PerformanceMetrics:
    """Compute institutional quantitative performance metrics from an equity curve and trade PnLs.

    Parameters:
        equity_series: Daily portfolio balance time series
        trade_pnls: List of realized net PnL dollar amounts per closed trade
        annualization_factor: Trading days per year (252 for daily forex)

    Returns:
        PerformanceMetrics dataclass
    """
    initial_balance = float(equity_series.iloc[0])
    final_balance = float(equity_series.iloc[-1])
    total_return_pct = ((final_balance - initial_balance) / initial_balance) * 100.0

    days = max(1, (equity_series.index[-1] - equity_series.index[0]).days)
    years = days / 365.25
    cagr_pct = ((final_balance / initial_balance) ** (1.0 / max(0.1, years)) - 1.0) * 100.0

    # Daily returns
    daily_returns = equity_series.pct_change().dropna()
    mean_ret = daily_returns.mean()
    std_ret = daily_returns.std()

    if std_ret > 0:
        annualized_vol = std_ret * np.sqrt(annualization_factor) * 100.0
        sharpe = (mean_ret / std_ret) * np.sqrt(annualization_factor)
    else:
        annualized_vol = 0.0
        sharpe = 0.0

    # Sortino (downside volatility only)
    downside_returns = daily_returns[daily_returns < 0.0]
    downside_std = downside_returns.std()
    if pd.notna(downside_std) and downside_std > 0:
        sortino = (mean_ret / downside_std) * np.sqrt(annualization_factor)
    elif len(downside_returns) == 0 and mean_ret > 0:
        sortino = 999.0  # Zero downside risk
    else:
        sortino = 0.0

    # Drawdowns
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max
    max_drawdown_pct = abs(float(drawdown.min())) * 100.0

    # Max drawdown duration
    is_drawdown = drawdown < 0.0
    duration = 0
    max_duration = 0
    for dd in is_drawdown:
        if dd:
            duration += 1
            max_duration = max(max_duration, duration)
        else:
            duration = 0

    if max_drawdown_pct > 0:
        calmar = cagr_pct / max_drawdown_pct
    elif cagr_pct > 0:
        calmar = 999.0  # Zero drawdown
    else:
        calmar = 0.0

    # Trade statistics
    total_trades = len(trade_pnls)
    if total_trades > 0:
        pnls = np.array(trade_pnls)
        wins = pnls[pnls > 0.0]
        losses = pnls[pnls < 0.0]

        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate_pct = (winning_trades / total_trades) * 100.0

        gross_profit = float(wins.sum()) if len(wins) > 0 else 0.0
        gross_loss = abs(float(losses.sum())) if len(losses) > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0

        avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
        avg_loss = abs(float(losses.mean())) if len(losses) > 0 else 0.0
        win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        avg_pnl = float(pnls.mean())
        expectancy = (win_rate_pct / 100.0 * avg_win) - ((1.0 - win_rate_pct / 100.0) * avg_loss)
    else:
        winning_trades = 0
        losing_trades = 0
        win_rate_pct = 0.0
        profit_factor = 0.0
        avg_win = 0.0
        avg_loss = 0.0
        win_loss_ratio = 0.0
        avg_pnl = 0.0
        expectancy = 0.0

    return PerformanceMetrics(
        initial_balance=initial_balance,
        final_balance=final_balance,
        total_return_pct=total_return_pct,
        cagr_pct=cagr_pct,
        annualized_volatility_pct=annualized_vol,
        sharpe_ratio=float(sharpe),
        sortino_ratio=float(sortino),
        calmar_ratio=float(calmar),
        max_drawdown_pct=max_drawdown_pct,
        max_drawdown_duration_days=max_duration,
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        avg_trade_pnl_usd=avg_pnl,
        avg_win_usd=avg_win,
        avg_loss_usd=avg_loss,
        win_loss_ratio=win_loss_ratio,
        expectancy_usd=expectancy,
    )
