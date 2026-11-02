"""Automated Trading Loop and Decision Engine for DareFX.

Coordinates:
1. Daily market bar ingest
2. Feature extraction (RSI, MACD, Bollinger, ATR, ADX, EMAs)
3. Production model inference (LightGBM)
4. Circuit Breaker validation (drawdown limit checks)
5. Regime filtering (ADX trend filter >= 32.0)
6. Position sizing (Fixed fractional 1.0% risk)
7. Telegram alert dispatching
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from darefx.data.storage import ParquetStorage
from darefx.features.technical import extract_features
from darefx.models.trainer import LightGBMTrainer
from darefx.notifications.telegram import TelegramNotifier
from darefx.risk.circuit_breaker import CircuitBreaker, CircuitState
from darefx.risk.position_sizing import calculate_fixed_fractional_lots
from darefx.trading.executor import ExecutionConfig, OrderExecutor
from darefx.trading.mt5_bridge import MT5Bridge

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BotConfig:
    """Trading loop operational configuration."""

    symbol: str = "EURUSD"
    model_path: str = "data/models/lightgbm_eurusd.joblib"
    data_dir: str = "data/processed"
    confidence_threshold: float = 0.40
    adx_min: float = 32.0
    pt_multiplier: float = 1.2
    sl_multiplier: float = 1.0
    risk_pct: float = 1.0
    leverage: float = 100.0
    execute_orders: bool = False


class TradingBot:
    """Autonomous trading bot execution controller."""

    def __init__(self, config: BotConfig = BotConfig()) -> None:
        self.config = config
        self.notifier = TelegramNotifier()
        self.circuit_breaker = CircuitBreaker()
        self.storage = ParquetStorage(base_dir=config.data_dir)
        self.bridge = MT5Bridge()
        self.executor = OrderExecutor(
            bridge=self.bridge,
            circuit_breaker=self.circuit_breaker,
            config=ExecutionConfig(risk_pct=config.risk_pct, leverage=config.leverage),
        )

    def run_daily_cycle(self, current_equity: float = 10_000.0) -> dict[str, Any]:
        """Execute one complete daily analysis and trading cycle."""
        now_utc = datetime.now(timezone.utc)
        date_str = now_utc.strftime("%Y-%m-%d")

        logger.info("Executing daily cycle for %s on %s...", self.config.symbol, date_str)

        # 1. Update circuit breaker status
        cb_status = self.circuit_breaker.update(current_equity=current_equity, current_date_str=date_str)
        allowed, cb_reason = self.circuit_breaker.can_open_new_trade()

        if not allowed:
            logger.warning("Trade generation blocked by circuit breaker: %s", cb_reason)
            self.notifier.notify_circuit_breaker(
                state=cb_status.state.value,
                reason=cb_reason,
                current_equity=current_equity,
                drawdown_pct=cb_status.peak_drawdown_pct,
            )
            return {
                "status": "blocked_by_circuit_breaker",
                "state": cb_status.state.value,
                "reason": cb_reason,
            }

        # 2. Load historical bars and update with live market feed
        df_bars = self.storage.load_daily_bars(symbol=self.config.symbol)
        try:
            from darefx.data.downloader import YahooFinanceDownloader
            downloader = YahooFinanceDownloader(symbol=f"{self.config.symbol}=X")
            live_bars = downloader.fetch_daily_bars(range_str="1mo")
            if not live_bars.empty:
                combined = pd.concat([df_bars, live_bars], ignore_index=True)
                combined["date_only"] = pd.to_datetime(combined["timestamp"]).dt.date
                combined = combined.drop_duplicates(subset=["date_only"], keep="last")
                df_bars = combined.drop(columns=["date_only"]).sort_values("timestamp").reset_index(drop=True)
                self.storage.save_daily_bars(df_bars, symbol=self.config.symbol)
        except Exception as err:
            logger.warning("Could not fetch live Yahoo Finance bars, continuing with local data: %s", err)

        if len(df_bars) < 205:
            err_msg = f"Insufficient bars ({len(df_bars)}) to compute 200-period indicators."
            logger.error(err_msg)
            return {"status": "error", "message": err_msg}

        df_features = extract_features(df_bars, dropna=True)
        latest_row = df_features.iloc[-1]
        latest_close = float(latest_row["close"])
        latest_atr = float(latest_row["atr_14"])
        latest_adx = float(latest_row["adx_14"])

        # 3. Load model and run inference
        model_file = Path(self.config.model_path)
        if not model_file.exists():
            err_msg = f"Model artifact not found at {model_file}."
            logger.error(err_msg)
            return {"status": "error", "message": err_msg}

        trainer = LightGBMTrainer.load(model_file)
        feature_vector = pd.DataFrame([latest_row[trainer.feature_names]])
        probs = trainer.predict_proba(feature_vector)[0]

        prob_sell = float(probs[0])
        prob_neutral = float(probs[1])
        prob_buy = float(probs[2])

        logger.info(
            "Inference results for %s: Buy=%.2f%%, Neutral=%.2f%%, Sell=%.2f%% | ADX=%.2f (Min=%.1f)",
            self.config.symbol, prob_buy * 100, prob_neutral * 100, prob_sell * 100, latest_adx, self.config.adx_min
        )

        # 4. Apply regime filter (ADX trend strength)
        if latest_adx < self.config.adx_min:
            reason = f"Market in chop/sideways consolidation (ADX {latest_adx:.1f} < {self.config.adx_min:.1f}). No trade."
            logger.info(reason)
            return {
                "status": "filtered_by_regime",
                "reason": reason,
                "probabilities": {"buy": prob_buy, "neutral": prob_neutral, "sell": prob_sell},
            }

        # 5. Check signal direction and confidence threshold
        direction = 0
        confidence = 0.0
        if prob_buy >= self.config.confidence_threshold and prob_buy > prob_sell:
            direction = 1
            confidence = prob_buy
        elif prob_sell >= self.config.confidence_threshold and prob_sell > prob_buy:
            direction = -1
            confidence = prob_sell

        if direction == 0:
            return {
                "status": "no_signal",
                "reason": f"Probabilities below threshold {self.config.confidence_threshold:.2f}",
                "probabilities": {"buy": prob_buy, "neutral": prob_neutral, "sell": prob_sell},
            }

        # 6. Calculate position sizing and protective barriers
        pt_dist = latest_atr * self.config.pt_multiplier
        sl_dist = latest_atr * self.config.sl_multiplier

        if direction == 1:
            action = "BUY"
            stop_loss = latest_close - sl_dist
            take_profit = latest_close + pt_dist
        else:
            action = "SELL"
            stop_loss = latest_close + sl_dist
            take_profit = latest_close - pt_dist

        sizing = calculate_fixed_fractional_lots(
            account_equity=current_equity,
            entry_price=latest_close,
            stop_loss_price=stop_loss,
            risk_pct=self.config.risk_pct,
            leverage=self.config.leverage,
        )

        # 7. Order Execution (if live/paper execution enabled)
        ticket = 0
        execution_status = "simulated"
        if self.config.execute_orders:
            self.bridge.connect()
            exec_rep = self.executor.execute_signal(
                symbol=self.config.symbol,
                action=action,
                current_price=latest_close,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            ticket = exec_rep.ticket
            execution_status = exec_rep.status
            execution_message = exec_rep.message
        else:
            execution_message = "Paper trading simulation"

        # 8. Dispatch Telegram alert only if order was actually executed or simulated
        if execution_status in ("executed", "simulated") and ticket > 0:
            self.notifier.notify_trade_opened(
                direction=action,
                symbol=self.config.symbol,
                lots=sizing.lots,
                entry_price=latest_close,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
            )

        logger.info("Signal generated: %s %.2f lots %s @ %.5f (Execution: %s, Ticket: #%d, Message: %s)",
                    action, sizing.lots, self.config.symbol, latest_close, execution_status, ticket, execution_message)

        return {
            "status": "signal_dispatched",
            "action": action,
            "lots": sizing.lots,
            "entry_price": latest_close,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "confidence": confidence,
            "adx": latest_adx,
            "execution_status": execution_status,
            "execution_message": execution_message,
            "ticket": ticket,
        }
