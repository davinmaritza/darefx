"""Multi-Asset Cross-Portfolio Backtester for DareFX.

Simulates synchronous portfolio allocation across Forex, Crypto, and Stocks,
enforcing PortfolioGovernor risk constraints, multi-asset capacity caps,
asymmetric take-profit/stop-loss barriers, and automated break-even trailing.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from darefx.risk.portfolio_governor import (
    AssetClass,
    PortfolioGovernor,
    PortfolioGovernorConfig,
    SignalCandidate,
)
from darefx.trading.mt5_bridge import OrderType, Position

logger = logging.getLogger(__name__)


@dataclass
class MultiAssetBacktestConfig:
    """Configuration parameters for multi-asset portfolio backtesting."""

    start_date: str = "2023-01-01"
    end_date: str = "2026-11-01"
    initial_equity: float = 10_000.0
    forex_symbols: list[str] = field(
        default_factory=lambda: ["EURUSD", "GBPUSD", "USDJPY"]
    )
    crypto_symbols: list[str] = field(
        default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    )
    stock_symbols: list[str] = field(
        default_factory=lambda: ["NVDA", "AAPL", "MSFT", "AMZN"]
    )
    risk_per_trade_pct: float = 1.0
    max_total_positions: int = 5
    max_positions_per_asset: dict[str, int] = field(
        default_factory=lambda: {"forex": 2, "crypto": 2, "stocks": 2}
    )
    take_profit_rr: float = 1.8
    trailing_be_threshold: float = 0.5  # Move to BE when price moves 50% towards TP


@dataclass
class AssetPerformance:
    """Performance breakdown for an individual asset class."""

    asset_class: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    profit_factor: float = 0.0


@dataclass
class SimulatedTrade:
    """Internal simulated trade structure."""

    ticket: int
    symbol: str
    asset_class: AssetClass
    action: str  # "BUY" or "SELL"
    entry_date: str
    entry_price: float
    stop_loss: float
    take_profit: float
    initial_risk: float
    be_active: bool = False
    exit_date: str | None = None
    exit_price: float = 0.0
    pnl: float = 0.0
    status: str = "OPEN"  # "WIN_TP", "LOSS_SL", "BREAKEVEN", "TIMEOUT"


@dataclass
class MultiAssetBacktestResult:
    """Synthesized outcome of multi-asset portfolio backtest."""

    initial_equity: float
    final_equity: float
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    max_drawdown_usd: float
    portfolio_sharpe: float
    portfolio_sortino: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    overall_win_rate: float
    overall_profit_factor: float
    asset_breakdown: dict[str, AssetPerformance]
    correlation_matrix: dict[str, dict[str, float]]
    equity_curve: pd.DataFrame
    trades: list[SimulatedTrade]


class MultiAssetBacktester:
    """Simulates multi-asset cross-portfolio performance over historical daily regimes."""

    def __init__(self, config: MultiAssetBacktestConfig | None = None) -> None:
        self.config = config or MultiAssetBacktestConfig()
        self.governor = PortfolioGovernor(
            PortfolioGovernorConfig(
                max_total_positions=self.config.max_total_positions,
                max_positions_per_asset=self.config.max_positions_per_asset,
                max_portfolio_risk_pct=5.0,
            )
        )

    def _generate_synthetic_series(
        self,
        symbol: str,
        asset_class: AssetClass,
        dates: list[str],
    ) -> pd.DataFrame:
        """Generate realistic daily OHLCV series for instruments lacking local raw data."""
        np.random.seed(abs(hash(symbol)) % (2**31))
        n = len(dates)

        if asset_class == AssetClass.FOREX:
            base_price = 1.1000 if "EUR" in symbol else 1.2500 if "GBP" in symbol else 145.0
            daily_vol = 0.0055
            drift = 0.00005
        elif asset_class == AssetClass.CRYPTO:
            base_price = 45000.0 if "BTC" in symbol else 2500.0 if "ETH" in symbol else 140.0
            daily_vol = 0.028
            drift = 0.0006
        else:  # STOCKS
            base_price = 120.0 if "NVDA" in symbol else 180.0 if "AAPL" in symbol else 400.0
            daily_vol = 0.016
            drift = 0.0004

        returns = np.random.normal(loc=drift, scale=daily_vol, size=n)
        price_curve = base_price * np.exp(np.cumsum(returns))

        highs = price_curve * (1.0 + np.abs(np.random.normal(0, daily_vol * 0.6, size=n)))
        lows = price_curve * (1.0 - np.abs(np.random.normal(0, daily_vol * 0.6, size=n)))
        opens = price_curve * (1.0 + np.random.normal(0, daily_vol * 0.3, size=n))
        closes = price_curve
        volumes = np.random.lognormal(mean=12.0, sigma=0.5, size=n)

        # Ensure high is maximum and low is minimum
        highs = np.maximum(highs, np.maximum(opens, closes))
        lows = np.minimum(lows, np.minimum(opens, closes))

        df = pd.DataFrame(
            {
                "date": dates,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            }
        )
        return df

    def _load_or_generate_data(self, dates: list[str]) -> dict[str, pd.DataFrame]:
        """Load local EUR/USD CSV if available, or generate consistent multi-asset history."""
        data_map: dict[str, pd.DataFrame] = {}
        eurusd_csv = Path("data/raw/eurusd_daily.csv")

        for sym in self.config.forex_symbols:
            if sym == "EURUSD" and eurusd_csv.exists():
                try:
                    df = pd.read_csv(eurusd_csv)
                    if "date" in df.columns and "close" in df.columns:
                        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                        df = df[df["date"].isin(dates)].reset_index(drop=True)
                        if len(df) >= len(dates) * 0.5:
                            data_map[sym] = df
                            continue
                except Exception as err:
                    logger.debug("Failed loading raw EUR/USD CSV: %s", err)
            data_map[sym] = self._generate_synthetic_series(sym, AssetClass.FOREX, dates)

        for sym in self.config.crypto_symbols:
            data_map[sym] = self._generate_synthetic_series(sym, AssetClass.CRYPTO, dates)

        for sym in self.config.stock_symbols:
            data_map[sym] = self._generate_synthetic_series(sym, AssetClass.STOCKS, dates)

        return data_map

    def run(self) -> MultiAssetBacktestResult:
        """Run day-by-day synchronized portfolio simulation."""
        # 1. Build chronological date timeline
        start_dt = datetime.date.fromisoformat(self.config.start_date)
        end_dt = datetime.date.fromisoformat(self.config.end_date)
        cur = start_dt
        dates: list[str] = []
        while cur <= end_dt:
            if cur.weekday() < 5:  # Business days
                dates.append(cur.isoformat())
            cur += datetime.timedelta(days=1)

        data_map = self._load_or_generate_data(dates)

        # 2. Simulation State Tracking
        equity = self.config.initial_equity
        equity_records: list[dict[str, Any]] = []
        active_trades: list[SimulatedTrade] = []
        closed_trades: list[SimulatedTrade] = []
        ticket_seq = 1000

        asset_class_map: dict[str, AssetClass] = {}
        for s in self.config.forex_symbols:
            asset_class_map[s] = AssetClass.FOREX
        for s in self.config.crypto_symbols:
            asset_class_map[s] = AssetClass.CRYPTO
        for s in self.config.stock_symbols:
            asset_class_map[s] = AssetClass.STOCKS

        daily_returns_by_asset: dict[str, list[float]] = {
            "forex": [],
            "crypto": [],
            "stocks": [],
        }

        # 3. Step Through Each Trading Day
        for i, current_date in enumerate(dates):
            if i < 20:  # Warm-up period for rolling indicators
                equity_records.append(
                    {
                        "date": current_date,
                        "equity": equity,
                        "drawdown_pct": 0.0,
                        "open_positions": 0,
                    }
                )
                continue

            day_pnl_by_asset = {"forex": 0.0, "crypto": 0.0, "stocks": 0.0}

            # A. Evaluate and Manage Active Trades
            remaining_trades: list[SimulatedTrade] = []
            for t in active_trades:
                df = data_map.get(t.symbol)
                if df is None or i >= len(df):
                    remaining_trades.append(t)
                    continue

                bar = df.iloc[i]
                high = float(bar["high"])
                low = float(bar["low"])

                exit_trade = False
                pnl = 0.0
                asset_key = t.asset_class.value.lower()

                if t.action == "BUY":
                    # Check Stop Loss
                    if low <= t.stop_loss:
                        exit_trade = True
                        pnl = (
                            0.0
                            if t.be_active
                            else -(t.initial_risk)
                        )
                        t.status = "BREAKEVEN" if t.be_active else "LOSS_SL"
                        t.exit_price = t.stop_loss
                    # Check Take Profit
                    elif high >= t.take_profit:
                        exit_trade = True
                        pnl = t.initial_risk * self.config.take_profit_rr
                        t.status = "WIN_TP"
                        t.exit_price = t.take_profit
                    else:
                        # Check Break-Even trigger
                        tp_dist = t.take_profit - t.entry_price
                        be_thresh = self.config.trailing_be_threshold
                        if tp_dist > 0 and (high - t.entry_price) >= tp_dist * be_thresh:
                            t.be_active = True
                            t.stop_loss = t.entry_price  # Lock at entry
                else:  # SELL
                    # Check Stop Loss
                    if high >= t.stop_loss:
                        exit_trade = True
                        pnl = (
                            0.0
                            if t.be_active
                            else -(t.initial_risk)
                        )
                        t.status = "BREAKEVEN" if t.be_active else "LOSS_SL"
                        t.exit_price = t.stop_loss
                    # Check Take Profit
                    elif low <= t.take_profit:
                        exit_trade = True
                        pnl = t.initial_risk * self.config.take_profit_rr
                        t.status = "WIN_TP"
                        t.exit_price = t.take_profit
                    else:
                        # Check Break-Even trigger
                        tp_dist = t.entry_price - t.take_profit
                        if (
                            tp_dist > 0
                            and (t.entry_price - low) >= tp_dist * self.config.trailing_be_threshold
                        ):
                            t.be_active = True
                            t.stop_loss = t.entry_price

                if exit_trade:
                    t.exit_date = current_date
                    t.pnl = pnl
                    equity += pnl
                    day_pnl_by_asset[asset_key] += pnl
                    closed_trades.append(t)
                else:
                    remaining_trades.append(t)

            active_trades = remaining_trades

            # B. Generate New Signals from Universe
            candidates: list[SignalCandidate] = []
            for symbol, df in data_map.items():
                if i >= len(df):
                    continue

                sub_df = df.iloc[: i + 1]
                closes_arr = sub_df["close"].to_numpy()
                ema_fast = float(np.mean(closes_arr[-9:]))
                ema_slow = float(np.mean(closes_arr[-21:]))
                cur_price = float(closes_arr[-1])
                asset_cls = asset_class_map[symbol]

                # Volatility via 14-bar range
                recent_range = float(
                    np.mean(sub_df["high"].iloc[-14:] - sub_df["low"].iloc[-14:])
                )
                atr = max(recent_range, cur_price * 0.005)

                action = None
                conf = 0.50
                # Momentum / Trend signal logic
                if cur_price > ema_fast > ema_slow:
                    action = "BUY"
                    conf = 0.65 + min(0.25, (cur_price - ema_slow) / ema_slow * 2.0)
                elif cur_price < ema_fast < ema_slow:
                    action = "SELL"
                    conf = 0.65 + min(0.25, (ema_slow - cur_price) / ema_slow * 2.0)

                if action:
                    sl_dist = atr * 1.5
                    tp_dist = sl_dist * self.config.take_profit_rr
                    sl = cur_price - sl_dist if action == "BUY" else cur_price + sl_dist
                    tp = cur_price + tp_dist if action == "BUY" else cur_price - tp_dist

                    candidates.append(
                        SignalCandidate(
                            asset_class=asset_cls,
                            symbol=symbol,
                            action=action,
                            entry_price=cur_price,
                            stop_loss=sl,
                            take_profit=tp,
                            confidence=conf,
                            atr=atr,
                            risk_reward_ratio=self.config.take_profit_rr,
                        )
                    )

            # C. Governor Gatekeeping & Order Allocation
            current_mock_positions = [
                Position(
                    ticket=t.ticket,
                    symbol=t.symbol,
                    order_type=OrderType.BUY if t.action == "BUY" else OrderType.SELL,
                    volume=1.0,
                    open_price=t.entry_price,
                    current_price=t.entry_price,
                    sl=t.stop_loss,
                    tp=t.take_profit,
                    profit=0.0,
                    open_time=datetime.datetime.now(datetime.UTC),
                )
                for t in active_trades
            ]

            approved_candidates = self.governor.rank_and_filter(
                candidates=candidates,
                current_positions=current_mock_positions,
                current_equity=equity,
            )

            # Open approved candidates
            trade_risk_budget = equity * (self.config.risk_per_trade_pct / 100.0)
            for c in approved_candidates:
                ticket_seq += 1
                new_trade = SimulatedTrade(
                    ticket=ticket_seq,
                    symbol=c.symbol,
                    asset_class=c.asset_class,
                    action=c.action,
                    entry_date=current_date,
                    entry_price=c.entry_price,
                    stop_loss=c.stop_loss,
                    take_profit=c.take_profit,
                    initial_risk=trade_risk_budget,
                )
                active_trades.append(new_trade)

            # Record daily equity & returns
            peak_equity = max([r["equity"] for r in equity_records] + [equity])
            dd_pct = (peak_equity - equity) / peak_equity * 100.0 if peak_equity > 0 else 0.0

            equity_records.append(
                {
                    "date": current_date,
                    "equity": equity,
                    "drawdown_pct": dd_pct,
                    "open_positions": len(active_trades),
                }
            )

            for ak in ["forex", "crypto", "stocks"]:
                daily_returns_by_asset[ak].append(day_pnl_by_asset[ak] / equity)

        # 4. Synthesize Final Metrics
        eq_df = pd.DataFrame(equity_records)
        initial_eq = self.config.initial_equity
        final_eq = equity
        total_ret_pct = (final_eq - initial_eq) / initial_eq * 100.0

        n_days = max(1, len(dates))
        ann_factor = 252.0 / n_days
        ann_ret_pct = total_ret_pct * ann_factor

        max_dd_pct = float(eq_df["drawdown_pct"].max()) if not eq_df.empty else 0.0
        peak_series = eq_df["equity"].cummax()
        drawdown_usd_series = peak_series - eq_df["equity"]
        max_dd_usd = float(drawdown_usd_series.max()) if not eq_df.empty else 0.0

        daily_returns = eq_df["equity"].pct_change().dropna().to_numpy()
        mean_ret = float(np.mean(daily_returns)) if len(daily_returns) > 0 else 0.0
        std_ret = float(np.std(daily_returns)) if len(daily_returns) > 0 else 1e-6
        sharpe = (mean_ret / std_ret) * np.sqrt(252.0) if std_ret > 0 else 0.0

        downside = daily_returns[daily_returns < 0]
        downside_std = float(np.std(downside)) if len(downside) > 0 else 1e-6
        sortino = (mean_ret / downside_std) * np.sqrt(252.0) if downside_std > 0 else 0.0

        # Breakdown by asset class
        breakdown: dict[str, AssetPerformance] = {}
        for a_cls in [AssetClass.FOREX, AssetClass.CRYPTO, AssetClass.STOCKS]:
            key = a_cls.value.lower()
            trades_in_class = [t for t in closed_trades if t.asset_class == a_cls]
            n_t = len(trades_in_class)
            w_t = len([t for t in trades_in_class if t.pnl > 0])
            l_t = len([t for t in trades_in_class if t.pnl < 0])
            gp = sum([t.pnl for t in trades_in_class if t.pnl > 0])
            gl = abs(sum([t.pnl for t in trades_in_class if t.pnl < 0]))
            np_val = gp - gl
            pf = gp / gl if gl > 0 else (99.0 if gp > 0 else 0.0)
            wr = (w_t / n_t * 100.0) if n_t > 0 else 0.0

            breakdown[key] = AssetPerformance(
                asset_class=a_cls.value.upper(),
                total_trades=n_t,
                wins=w_t,
                losses=l_t,
                win_rate=wr,
                gross_profit=gp,
                gross_loss=gl,
                net_profit=np_val,
                profit_factor=pf,
            )

        # Cross-asset return correlations
        corr_matrix: dict[str, dict[str, float]] = {}
        keys = ["forex", "crypto", "stocks"]
        for k1 in keys:
            corr_matrix[k1] = {}
            s1 = pd.Series(daily_returns_by_asset[k1])
            for k2 in keys:
                s2 = pd.Series(daily_returns_by_asset[k2])
                corr = float(s1.corr(s2)) if len(s1) > 1 and s1.std() > 0 and s2.std() > 0 else 0.0
                corr_matrix[k1][k2] = round(corr, 3) if not np.isnan(corr) else 0.0

        n_all_trades = len(closed_trades)
        w_all = len([t for t in closed_trades if t.pnl > 0])
        l_all = len([t for t in closed_trades if t.pnl < 0])
        gross_p_all = sum([t.pnl for t in closed_trades if t.pnl > 0])
        gross_l_all = abs(sum([t.pnl for t in closed_trades if t.pnl < 0]))
        pf_all = (
            gross_p_all / gross_l_all
            if gross_l_all > 0
            else (99.0 if gross_p_all > 0 else 0.0)
        )
        wr_all = (w_all / n_all_trades * 100.0) if n_all_trades > 0 else 0.0

        return MultiAssetBacktestResult(
            initial_equity=initial_eq,
            final_equity=final_eq,
            total_return_pct=total_ret_pct,
            annualized_return_pct=ann_ret_pct,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_usd=max_dd_usd,
            portfolio_sharpe=sharpe,
            portfolio_sortino=sortino,
            total_trades=n_all_trades,
            winning_trades=w_all,
            losing_trades=l_all,
            overall_win_rate=wr_all,
            overall_profit_factor=pf_all,
            asset_breakdown=breakdown,
            correlation_matrix=corr_matrix,
            equity_curve=eq_df,
            trades=closed_trades,
        )
