"""Model training and evaluation module for DareFX.

Specialized in tabular gradient-boosted decision trees (LightGBM and XGBoost)
configured for 3-class Triple Barrier classification:
- Class 0: Sell / Short (Target -1, stop loss / downward break)
- Class 1: Neutral / No-Trade (Target 0, vertical barrier expiry)
- Class 2: Buy / Long (Target +1, profit target / upward break)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, log_loss
import xgboost as xgb

from darefx.models.validator import WalkForwardConfig, WalkForwardFold, WalkForwardSplitter

logger = logging.getLogger(__name__)

# Target mapping between raw labels (-1, 0, 1) and zero-indexed multi-class indices (0, 1, 2)
LABEL_TO_INT = {-1: 0, 0: 1, 1: 2}
INT_TO_LABEL = {0: -1, 1: 0, 2: 1}
CLASS_NAMES = ["Sell (-1)", "Neutral (0)", "Buy (+1)"]


@dataclass
class WalkForwardEvaluationResult:
    """Summary of out-of-sample walk-forward validation performance."""

    num_folds: int
    total_samples: int
    overall_accuracy: float
    overall_log_loss: float
    class_report: dict[str, Any]
    feature_importance: pd.DataFrame
    out_of_sample_df: pd.DataFrame


@dataclass
class LightGBMConfig:
    """Hyperparameter configuration for the LightGBM classifier."""

    n_estimators: int = 250
    learning_rate: float = 0.03
    max_depth: int = 4
    num_leaves: int = 15
    min_child_samples: int = 35
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.0
    reg_lambda: float = 0.0
    random_state: int = 42
    class_weight: str | None = "balanced"


class LightGBMTrainer:
    """Trainer and evaluator for LightGBM on financial time-series."""

    def __init__(self, config: LightGBMConfig = LightGBMConfig()) -> None:
        self.config = config
        self.model: lgb.LGBMClassifier | None = None
        self.feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> LightGBMTrainer:
        """Fit a single LightGBM model on training data."""
        self.feature_names = list(X.columns)
        y_encoded = y.map(LABEL_TO_INT).values

        self.model = lgb.LGBMClassifier(
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            max_depth=self.config.max_depth,
            num_leaves=self.config.num_leaves,
            min_child_samples=self.config.min_child_samples,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            reg_alpha=self.config.reg_alpha,
            reg_lambda=self.config.reg_lambda,
            random_state=self.config.random_state,
            class_weight=self.config.class_weight,
            objective="multiclass",
            num_class=3,
            verbosity=-1,
            n_jobs=-1,
        )


        self.model.fit(X, y_encoded)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict class probabilities: [P(Sell), P(Neutral), P(Buy)]."""
        if self.model is None:
            raise RuntimeError("Model is not fitted yet. Call fit() first.")
        return self.model.predict_proba(X)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict original target labels: -1, 0, or 1."""
        probs = self.predict_proba(X)
        int_preds = np.argmax(probs, axis=1)
        return np.array([INT_TO_LABEL[p] for p in int_preds])

    def get_feature_importance(self) -> pd.DataFrame:
        """Extract feature importance ranked by total gain."""
        if self.model is None:
            raise RuntimeError("Model is not fitted yet.")

        importance = self.model.booster_.feature_importance(importance_type="gain")
        df_imp = pd.DataFrame(
            {
                "feature": self.feature_names,
                "importance_gain": importance,
            }
        ).sort_values("importance_gain", ascending=False).reset_index(drop=True)

        return df_imp

    def evaluate_walk_forward(
        self,
        df_dataset: pd.DataFrame,
        feature_cols: list[str],
        target_col: str = "barrier_target",
        time_col: str = "timestamp",
        wf_config: WalkForwardConfig = WalkForwardConfig(),
    ) -> WalkForwardEvaluationResult:
        """Run a complete out-of-sample walk-forward validation across chronological folds.

        Parameters:
            df_dataset: DataFrame containing features, target, and timestamp
            feature_cols: List of predictor feature column names
            target_col: Name of the target column (-1, 0, 1)
            time_col: Name of the timestamp column
            wf_config: WalkForwardConfig specifying train/test window sizes

        Returns:
            WalkForwardEvaluationResult with full out-of-sample predictions and metrics
        """
        splitter = WalkForwardSplitter(config=wf_config)
        folds = splitter.split(df_dataset, time_col=time_col)

        if not folds:
            raise ValueError("No valid walk-forward folds generated. Check dataset length and window sizes.")

        oos_predictions: list[pd.DataFrame] = []
        feature_importances: list[pd.DataFrame] = []

        X_full = df_dataset[feature_cols]
        y_full = df_dataset[target_col]

        logger.info("Executing Walk-Forward evaluation over %d folds...", len(folds))

        for fold in folds:
            X_train = X_full.iloc[fold.train_indices]
            y_train = y_full.iloc[fold.train_indices]

            X_test = X_full.iloc[fold.test_indices]
            y_test = y_full.iloc[fold.test_indices]

            fold_model = LightGBMTrainer(config=self.config)
            fold_model.fit(X_train, y_train)

            probs = fold_model.predict_proba(X_test)
            preds = np.argmax(probs, axis=1)
            raw_preds = np.array([INT_TO_LABEL[p] for p in preds])

            fold_oos = df_dataset.iloc[fold.test_indices].copy()
            fold_oos["fold"] = fold.fold_idx
            fold_oos["pred_label"] = raw_preds
            fold_oos["prob_sell"] = probs[:, 0]
            fold_oos["prob_neutral"] = probs[:, 1]
            fold_oos["prob_buy"] = probs[:, 2]

            oos_predictions.append(fold_oos)
            feature_importances.append(fold_model.get_feature_importance())

        df_oos = pd.concat(oos_predictions, ignore_index=True)
        # Drop duplicates if folds overlap due to step < test window (keep latest fold)
        df_oos = df_oos.drop_duplicates(subset=[time_col], keep="last").sort_values(time_col).reset_index(drop=True)

        y_true_encoded = df_oos[target_col].map(LABEL_TO_INT).values
        pred_probs = df_oos[["prob_sell", "prob_neutral", "prob_buy"]].values
        pred_labels = df_oos["pred_label"].map(LABEL_TO_INT).values

        overall_acc = float(np.mean(y_true_encoded == pred_labels))
        overall_loss = float(log_loss(y_true_encoded, pred_probs, labels=[0, 1, 2]))
        report = classification_report(y_true_encoded, pred_labels, target_names=CLASS_NAMES, output_dict=True)

        # Average feature importance across all folds
        all_imp = pd.concat(feature_importances)
        avg_imp = all_imp.groupby("feature")["importance_gain"].mean().reset_index()
        avg_imp = avg_imp.sort_values("importance_gain", ascending=False).reset_index(drop=True)

        return WalkForwardEvaluationResult(
            num_folds=len(folds),
            total_samples=len(df_oos),
            overall_accuracy=overall_acc,
            overall_log_loss=overall_loss,
            class_report=report,  # type: ignore[arg-type]
            feature_importance=avg_imp,
            out_of_sample_df=df_oos,
        )

    def save(self, output_path: Path | str) -> None:
        """Persist model and metadata to disk."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "model": self.model,
            "config": self.config,
            "feature_names": self.feature_names,
        }
        joblib.dump(artifact, path)
        logger.info("Saved model artifact to %s", path)

    @classmethod
    def load(cls, model_path: Path | str) -> LightGBMTrainer:
        """Load model artifact from disk."""
        artifact = joblib.load(model_path)
        trainer = cls(config=artifact["config"])
        trainer.model = artifact["model"]
        trainer.feature_names = artifact["feature_names"]
        return trainer


@dataclass
class XGBoostConfig:
    """Hyperparameter configuration for the XGBoost classifier."""

    n_estimators: int = 200
    learning_rate: float = 0.03
    max_depth: int = 4
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    random_state: int = 42


class XGBoostTrainer:
    """Trainer and evaluator for XGBoost on financial time-series."""

    def __init__(self, config: XGBoostConfig = XGBoostConfig()) -> None:
        self.config = config
        self.model: xgb.XGBClassifier | None = None
        self.feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> XGBoostTrainer:
        """Fit a single XGBoost model on training data."""
        self.feature_names = list(X.columns)
        y_encoded = y.map(LABEL_TO_INT).values

        self.model = xgb.XGBClassifier(
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            max_depth=self.config.max_depth,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            random_state=self.config.random_state,
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            n_jobs=-1,
        )

        self.model.fit(X, y_encoded)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict class probabilities: [P(Sell), P(Neutral), P(Buy)]."""
        if self.model is None:
            raise RuntimeError("Model is not fitted yet. Call fit() first.")
        return self.model.predict_proba(X)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict original target labels: -1, 0, or 1."""
        probs = self.predict_proba(X)
        int_preds = np.argmax(probs, axis=1)
        return np.array([INT_TO_LABEL[p] for p in int_preds])

    def get_feature_importance(self) -> pd.DataFrame:
        """Extract feature importance ranked by gain."""
        if self.model is None:
            raise RuntimeError("Model is not fitted yet.")

        importance = self.model.feature_importances_
        df_imp = pd.DataFrame(
            {
                "feature": self.feature_names,
                "importance_gain": importance,
            }
        ).sort_values("importance_gain", ascending=False).reset_index(drop=True)

        return df_imp

    def evaluate_walk_forward(
        self,
        df_dataset: pd.DataFrame,
        feature_cols: list[str],
        target_col: str = "barrier_target",
        time_col: str = "timestamp",
        wf_config: WalkForwardConfig = WalkForwardConfig(),
    ) -> WalkForwardEvaluationResult:
        """Run a complete out-of-sample walk-forward validation across chronological folds."""
        splitter = WalkForwardSplitter(config=wf_config)
        folds = splitter.split(df_dataset, time_col=time_col)

        if not folds:
            raise ValueError("No valid walk-forward folds generated.")

        oos_predictions: list[pd.DataFrame] = []
        feature_importances: list[pd.DataFrame] = []

        X_full = df_dataset[feature_cols]
        y_full = df_dataset[target_col]

        logger.info("Executing XGBoost Walk-Forward evaluation over %d folds...", len(folds))

        for fold in folds:
            X_train = X_full.iloc[fold.train_indices]
            y_train = y_full.iloc[fold.train_indices]

            X_test = X_full.iloc[fold.test_indices]

            fold_model = XGBoostTrainer(config=self.config)
            fold_model.fit(X_train, y_train)

            probs = fold_model.predict_proba(X_test)
            preds = np.argmax(probs, axis=1)
            raw_preds = np.array([INT_TO_LABEL[p] for p in preds])

            fold_oos = df_dataset.iloc[fold.test_indices].copy()
            fold_oos["fold"] = fold.fold_idx
            fold_oos["pred_label"] = raw_preds
            fold_oos["prob_sell"] = probs[:, 0]
            fold_oos["prob_neutral"] = probs[:, 1]
            fold_oos["prob_buy"] = probs[:, 2]

            oos_predictions.append(fold_oos)
            feature_importances.append(fold_model.get_feature_importance())

        df_oos = pd.concat(oos_predictions, ignore_index=True)
        df_oos = df_oos.drop_duplicates(subset=[time_col], keep="last").sort_values(time_col).reset_index(drop=True)

        y_true_encoded = df_oos[target_col].map(LABEL_TO_INT).values
        pred_probs = df_oos[["prob_sell", "prob_neutral", "prob_buy"]].values
        pred_labels = df_oos["pred_label"].map(LABEL_TO_INT).values

        overall_acc = float(np.mean(y_true_encoded == pred_labels))
        overall_loss = float(log_loss(y_true_encoded, pred_probs, labels=[0, 1, 2]))
        report = classification_report(y_true_encoded, pred_labels, target_names=CLASS_NAMES, output_dict=True)

        all_imp = pd.concat(feature_importances)
        avg_imp = all_imp.groupby("feature")["importance_gain"].mean().reset_index()
        avg_imp = avg_imp.sort_values("importance_gain", ascending=False).reset_index(drop=True)

        return WalkForwardEvaluationResult(
            num_folds=len(folds),
            total_samples=len(df_oos),
            overall_accuracy=overall_acc,
            overall_log_loss=overall_loss,
            class_report=report,  # type: ignore[arg-type]
            feature_importance=avg_imp,
            out_of_sample_df=df_oos,
        )

    def save(self, output_path: Path | str) -> None:
        """Persist model and metadata to disk."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "model": self.model,
            "config": self.config,
            "feature_names": self.feature_names,
        }
        joblib.dump(artifact, path)
        logger.info("Saved XGBoost model artifact to %s", path)

    @classmethod
    def load(cls, model_path: Path | str) -> XGBoostTrainer:
        """Load XGBoost model artifact from disk."""
        artifact = joblib.load(model_path)
        trainer = cls(config=artifact["config"])
        trainer.model = artifact["model"]
        trainer.feature_names = artifact["feature_names"]
        return trainer

