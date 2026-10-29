"""Realistic event-driven backtesting engine for DareFX.

Simulates execution strictly on out-of-sample prediction streams:
1. Signal at day T close -> filled at day T+1 open (zero execution look-ahead).
2. Conservative transaction friction:
   - Round-trip spread: 1.5 pips
   - Slippage: 1.0 pip per fill
   - Commission: $7.00 per standard lot
3. Dynamic position sizing: Fixed fractional risk (default 1.0% of portfolio equity).
4. Generates daily equity curve and full trade log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

import numpy as np
import pandas as pd

from darefx.backtest.metrics import PerformanceMetrics, calculate_metrics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration parameters for trade simulation."""

    initial_capital: float = 10_000.0  # Starting balance in USD
    risk_per_trade_pct: float = 1.0     # Percent of current equity risked per trade (1.0%)
    spread_pips: float = 1.5           # Bid/ask spread in pips (1.5 pips = 0.00015)
    slippage_pips: float = 1.0         # Execution slippage in pips
    commission_per_lot: float = 7.00   # ECN commission per standard lot round-trip
    confidence_threshold: float = 0.40  # Minimum model probability to trigger trade
    max_holding_bars: int = 5          # Vertical barrier timeout
    pt_multiplier: float = 1.5         # Profit target barrier (x ATR)
    sl_multiplier: float = 1.5         # Stop loss barrier (x ATR)


@dataclass
class TradeRecord:
    """Record of an individual executed trade."""

    trade_id: int
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    direction: int  # 1 for Long, -1 for Short
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    position_units: float
    gross_pnl_usd: float
    friction_cost_usd: float
    net_pnl_usd: float
    return_pct: float
    exit_reason: str


@dataclass
class BacktestResult:
    """Complete output of backtest simulation."""

    config: BacktestConfig
    metrics: PerformanceMetrics
    equity_curve: pd.Series
    trade_log: pd.DataFrame


class BacktestEngine:
    """Event-driven simulator for out-of-sample trading strategies."""

    def __init__(self, config: BacktestConfig = BacktestConfig()) -> None:
        self.config = config

    def run(self, df_oos: pd.DataFrame) -> BacktestResult:
        """Run simulation over out-of-sample predictions DataFrame.

        Parameters:
            df_oos: DataFrame containing:
                ['timestamp', 'open', 'high', 'low', 'close', 'atr_14',
                 'prob_sell', 'prob_neutral', 'prob_buy']

        Returns:
            BacktestResult containing performance metrics, equity series, and trade log
        """
        if df_oos.empty:
            raise ValueError("Empty out-of-sample DataFrame provided to backtest engine.")

        df = df_oos.sort_values("timestamp").reset_index(drop=True)
        n = len(df)

        equity = self.config.initial_capital
        equity_records: list[tuple[pd.Timestamp, float]] = []
        trades: list[TradeRecord] = []

        timestamps = pd.to_datetime(df["timestamp"], utc=True)
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        atrs = df["atr_14"].values if "atr_14" in df.columns else (closes * 0.005)

        prob_buys = df["prob_buy"].values if "prob_buy" in df.columns else np.zeros(n)
        prob_sells = df["prob_sell"].values if "prob_sell" in df.columns else np.zeros(n)

        pip_cost = (self.config.spread_pips + self.config.slippage_pips) * 0.0001
        trade_id = 0
        i = 0

        while i < n - 1:
            curr_date = timestamps[i]
            equity_records.append((curr_date, equity))

            # Check signal at close of day T
            p_buy = prob_buys[i]
            p_sell = prob_sells[i]

            signal = 0
            if p_buy >= self.config.confidence_threshold and p_buy > p_sell:
                signal = 1
            elif p_sell >= self.config.confidence_threshold and p_sell > p_buy:
                signal = -1

            if signal == 0:
                i += 1
                continue

            # Execution happens at open of day T+1
            entry_idx = i + 1
            entry_date = timestamps[entry_idx]
            base_open = opens[entry_idx]

            atr = atrs[i]
            if np.isnan(atr) or atr <= 0:
                atr = base_open * 0.005

            sl_dist = atr * self.config.sl_multiplier
            pt_dist = atr * self.config.pt_multiplier

            # Position sizing: risk exactly risk_per_trade_pct of current equity
            risk_usd = equity * (self.config.risk_per_trade_pct / 100.0)
            # Units = Risk ($) / Stop distance ($ per unit)
            units = risk_usd / sl_dist
            # Cap maximum leverage to 10x for institutional prudence
            max_units = (equity * 10.0) / base_open
            units = min(units, max_units)

            lots = units / 100_000.0
            commission = lots * self.config.commission_per_lot

            if signal == 1:
                # Long Trade
                entry_price = base_open + pip_cost  # Pay ask
                take_profit = entry_price + pt_dist
                stop_loss = entry_price - sl_dist

                exit_price = entry_price
                exit_idx = entry_idx
                exit_reason = "time_expiry"

                max_bar = min(entry_idx + self.config.max_holding_bars, n - 1)
                for j in range(entry_idx, max_bar + 1):
                    h = highs[j]
                    l = lows[j]

                    if l <= stop_loss and h >= take_profit:
                        exit_price = stop_loss - (self.config.slippage_pips * 0.0001)
                        exit_idx = j
                        exit_reason = "stop_loss"
                        break
                    elif l <= stop_loss:
                        exit_price = stop_loss - (self.config.slippage_pips * 0.0001)
                        exit_idx = j
                        exit_reason = "stop_loss"
                        break
                    elif h >= take_profit:
                        exit_price = take_profit - (self.config.slippage_pips * 0.0001)
                        exit_idx = j
                        exit_reason = "profit_target"
                        break

                if exit_reason == "time_expiry":
                    exit_price = closes[max_bar] - (self.config.slippage_pips * 0.0001)
                    exit_idx = max_bar

                gross_pnl = (exit_price - entry_price) * units
                friction = (pip_cost * units) + commission
                net_pnl = gross_pnl - friction

            else:
                # Short Trade
                entry_price = base_open - pip_cost  # Sell at bid
                take_profit = entry_price - pt_dist
                stop_loss = entry_price + sl_dist

                exit_price = entry_price
                exit_idx = entry_idx
                exit_reason = "time_expiry"

                max_bar = min(entry_idx + self.config.max_holding_bars, n - 1)
                for j in range(entry_idx, max_bar + 1):
                    h = highs[j]
                    l = lows[j]

                    if h >= stop_loss and l <= take_profit:
                        exit_price = stop_loss + (self.config.slippage_pips * 0.0001)
                        exit_idx = j
                        exit_reason = "stop_loss"
                        break
                    elif h >= stop_loss:
                        exit_price = stop_loss + (self.config.slippage_pips * 0.0001)
                        exit_idx = j
                        exit_reason = "stop_loss"
                        break
                    elif l <= take_profit:
                        exit_price = take_profit + (self.config.slippage_pips * 0.0001)
                        exit_idx = j
                        exit_reason = "profit_target"
                        break

                if exit_reason == "time_expiry":
                    exit_price = closes[max_bar] + (self.config.slippage_pips * 0.0001)
                    exit_idx = max_bar

                gross_pnl = (entry_price - exit_price) * units
                friction = (pip_cost * units) + commission
                net_pnl = gross_pnl - friction

            trade_id += 1
            ret_pct = (net_pnl / equity) * 100.0
            equity = max(100.0, equity + net_pnl)  # Circuit floor

            trades.append(
                TradeRecord(
                    trade_id=trade_id,
                    entry_date=entry_date,
                    exit_date=timestamps[exit_idx],
                    direction=signal,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    position_units=units,
                    gross_pnl_usd=gross_pnl,
                    friction_cost_usd=friction,
                    net_pnl_usd=net_pnl,
                    return_pct=ret_pct,
                    exit_reason=exit_reason,
                )
            )

            # Advance simulator past trade exit to prevent overlapping position clutter
            i = exit_idx + 1

        # Final equity record
        equity_records.append((timestamps.iloc[-1], equity))
        df_equity = pd.DataFrame(equity_records, columns=["timestamp", "equity"])
        df_equity = df_equity.drop_duplicates(subset=["timestamp"], keep="last").set_index("timestamp")["equity"]

        trade_pnls = [t.net_pnl_usd for t in trades]
        metrics = calculate_metrics(df_equity, trade_pnls)

        trade_dicts = [t.__dict__ for t in trades]
        df_trades = pd.DataFrame(trade_dicts) if trade_dicts else pd.DataFrame()

        return BacktestResult(
            config=self.config,
            metrics=metrics,
            equity_curve=df_equity,
            trade_log=df_trades,
        )
