"""Optuna-powered Bayesian hyperparameter and execution policy optimizer for DareFX.

Optimizes:
1. Tree hyperparameters (learning rate, depth, leaves, child weight)
2. Execution confidence threshold (minimum probability required to enter)
3. Trend strength regime filter (minimum ADX required to trade, eliminating sideways chop)
4. Barrier multipliers (profit-taking and stop-loss widths)

Objective: Maximize out-of-sample Sharpe Ratio under realistic transaction friction.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import numpy as np
import optuna
import pandas as pd

from darefx.backtest.engine import BacktestConfig, BacktestEngine
from darefx.backtest.metrics import calculate_metrics
from darefx.features.labels import TripleBarrierConfig, apply_triple_barrier
from darefx.models.trainer import LightGBMConfig, LightGBMTrainer
from darefx.models.validator import WalkForwardConfig, WalkForwardSplitter

# Suppress verbose Optuna logging
optuna.logging.set_verbosity(optuna.logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class TuningResult:
    """Best parameters and performance achieved through Optuna optimization."""

    best_value: float
    best_params: dict[str, Any]
    study: optuna.Study


class HyperparameterTuner:
    """Orchestrates Bayesian parameter searches across out-of-sample cross-validation folds."""

    def __init__(
        self,
        df_features: pd.DataFrame,
        feature_cols: list[str],
        n_trials: int = 30,
        target_metric: str = "sharpe",  # 'sharpe' or 'profit_factor'
    ) -> None:
        self.df_features = df_features.sort_values("timestamp").reset_index(drop=True)
        self.feature_cols = feature_cols
        self.n_trials = n_trials
        self.target_metric = target_metric

    def optimize_execution_policy(
        self,
        df_oos: pd.DataFrame,
    ) -> dict[str, Any]:
        """Fast grid/Bayesian search over execution threshold, regime filter, and barriers

        on already generated out-of-sample prediction streams.
        """
        def objective(trial: optuna.Trial) -> float:
            threshold = trial.suggest_float("threshold", 0.38, 0.55, step=0.01)
            adx_min = trial.suggest_float("adx_min", 12.0, 32.0, step=2.0)
            sl_mult = trial.suggest_float("sl_multiplier", 1.0, 2.0, step=0.2)
            pt_mult = trial.suggest_float("pt_multiplier", 1.2, 2.4, step=0.2)

            # Filter predictions by regime: only take trades when ADX >= adx_min
            df_filtered = df_oos.copy()
            if "adx_14" in df_filtered.columns:
                weak_trend_mask = df_filtered["adx_14"] < adx_min
                df_filtered.loc[weak_trend_mask, "prob_buy"] = 0.0
                df_filtered.loc[weak_trend_mask, "prob_sell"] = 0.0

            config = BacktestConfig(
                initial_capital=10_000.0,
                risk_per_trade_pct=1.0,
                spread_pips=1.5,
                slippage_pips=1.0,
                confidence_threshold=threshold,
                sl_multiplier=sl_mult,
                pt_multiplier=pt_mult,
            )

            engine = BacktestEngine(config=config)
            result = engine.run(df_filtered)
            m = result.metrics

            # Enforce statistical significance: must execute at least 50 trades
            if m.total_trades < 50:
                return -10.0

            # Penalize excessive drawdown > 25%
            if m.max_drawdown_pct > 25.0:
                return -5.0 + (m.sharpe_ratio * 0.1)

            if self.target_metric == "sharpe":
                return float(m.sharpe_ratio)
            else:
                return float(m.profit_factor)

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=self.n_trials)

        logger.info("Optimization complete. Best %s: %.2f", self.target_metric, study.best_value)
        return {
            "best_score": study.best_value,
            "best_params": study.best_params,
        }
