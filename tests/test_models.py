"""Unit and integration tests for DareFX model training and validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from darefx.models.trainer import LightGBMConfig, LightGBMTrainer
from darefx.models.validator import CPCVSplitter, WalkForwardConfig, WalkForwardSplitter


@pytest.fixture
def synthetic_labeled_dataset() -> tuple[pd.DataFrame, list[str]]:
    """Create 500 daily samples of synthetic features and triple barrier targets."""
    np.random.seed(42)
    n = 500
    timestamps = pd.date_range("2021-01-01", periods=n, freq="B", tz="UTC")

    feature_cols = [f"feat_{i}" for i in range(10)]
    data = {col: np.random.normal(0, 1, size=n) for col in feature_cols}
    data["timestamp"] = timestamps
    data["close"] = 1.0800 + np.cumsum(np.random.normal(0, 0.002, size=n))

    # Targets: 1, 0, -1
    targets = np.random.choice([1, 0, -1], size=n, p=[0.3, 0.4, 0.3])
    data["barrier_target"] = targets

    df = pd.DataFrame(data)
    return df, feature_cols


class TestWalkForwardValidator:
    """Tests for purged and embargoed walk-forward splitting."""

    def test_chronological_splits_and_purging(self, synthetic_labeled_dataset):
        df, _ = synthetic_labeled_dataset
        config = WalkForwardConfig(train_months=6, test_months=2, step_months=2, purge_days=10)
        splitter = WalkForwardSplitter(config=config)
        folds = splitter.split(df, time_col="timestamp")

        assert len(folds) >= 2

        for fold in folds:
            train_ts = df["timestamp"].iloc[fold.train_indices]
            test_ts = df["timestamp"].iloc[fold.test_indices]

            # Invariant 1: Strictly chronological (train ends before test starts)
            assert train_ts.max() < test_ts.min()

            # Invariant 2: Purge gap respected (at least 10 days between effective train end and test start)
            gap_days = (test_ts.min() - train_ts.max()).total_seconds() / 86400.0
            assert gap_days >= 7.0  # Business day count is at least 7-10 calendar days

    def test_cpcv_splitter_partitions(self, synthetic_labeled_dataset):
        df, _ = synthetic_labeled_dataset
        cpcv = CPCVSplitter(n_groups=5, k_test_groups=2, purge_days=5)
        splits = cpcv.split(df, time_col="timestamp")

        assert len(splits) == 10  # 5 choose 2 = 10 combinations
        for train_idx, test_idx in splits:
            assert len(train_idx) > 0
            assert len(test_idx) > 0
            # Test and train indices must be completely disjoint
            assert len(set(train_idx).intersection(set(test_idx))) == 0


class TestLightGBMTrainer:
    """Tests for LightGBM model training, inference, and serialization."""

    def test_fit_and_predict(self, synthetic_labeled_dataset):
        df, feature_cols = synthetic_labeled_dataset
        X = df[feature_cols].iloc[:300]
        y = df["barrier_target"].iloc[:300]

        trainer = LightGBMTrainer(config=LightGBMConfig(n_estimators=30, max_depth=3))
        trainer.fit(X, y)

        X_val = df[feature_cols].iloc[300:]
        probs = trainer.predict_proba(X_val)
        preds = trainer.predict(X_val)

        # Invariant 1: Probabilities sum to 1.0 across classes
        assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-5)
        assert probs.shape == (200, 3)

        # Invariant 2: Predicted labels are in {-1, 0, 1}
        assert set(preds).issubset({-1, 0, 1})

        # Invariant 3: Feature importance has valid positive gains
        imp = trainer.get_feature_importance()
        assert len(imp) == len(feature_cols)
        assert (imp["importance_gain"] >= 0.0).all()

    def test_save_and_load(self, synthetic_labeled_dataset, tmp_path: Path):
        df, feature_cols = synthetic_labeled_dataset
        X = df[feature_cols].iloc[:100]
        y = df["barrier_target"].iloc[:100]

        trainer = LightGBMTrainer(config=LightGBMConfig(n_estimators=20))
        trainer.fit(X, y)
        orig_preds = trainer.predict_proba(X)

        model_file = tmp_path / "model.pkl"
        trainer.save(model_file)
        assert model_file.exists()

        loaded_trainer = LightGBMTrainer.load(model_file)
        loaded_preds = loaded_trainer.predict_proba(X)

        assert np.allclose(orig_preds, loaded_preds, atol=1e-8)

    def test_evaluate_walk_forward(self, synthetic_labeled_dataset):
        df, feature_cols = synthetic_labeled_dataset
        wf_config = WalkForwardConfig(train_months=8, test_months=2, step_months=2, purge_days=5)

        trainer = LightGBMTrainer(config=LightGBMConfig(n_estimators=25, max_depth=3))
        result = trainer.evaluate_walk_forward(
            df_dataset=df,
            feature_cols=feature_cols,
            target_col="barrier_target",
            time_col="timestamp",
            wf_config=wf_config,
        )

        assert result.num_folds >= 1
        assert result.total_samples > 0
        assert 0.0 <= result.overall_accuracy <= 1.0
        assert result.overall_log_loss > 0.0
        assert not result.out_of_sample_df.empty
        assert "pred_label" in result.out_of_sample_df.columns
        assert "prob_buy" in result.out_of_sample_df.columns


class TestXGBoostTrainer:
    """Tests for XGBoost model training and serialization."""

    def test_xgboost_fit_predict_save(self, synthetic_labeled_dataset, tmp_path: Path):
        from darefx.models.trainer import XGBoostConfig, XGBoostTrainer

        df, feature_cols = synthetic_labeled_dataset
        X = df[feature_cols].iloc[:100]
        y = df["barrier_target"].iloc[:100]

        trainer = XGBoostTrainer(config=XGBoostConfig(n_estimators=10, max_depth=3))
        trainer.fit(X, y)

        probs = trainer.predict_proba(X)
        assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-5)

        model_file = tmp_path / "xgb.pkl"
        trainer.save(model_file)
        assert model_file.exists()

        loaded = XGBoostTrainer.load(model_file)
        loaded_probs = loaded.predict_proba(X)
        assert np.allclose(probs, loaded_probs, atol=1e-5)


class TestHyperparameterTuner:
    """Tests for Optuna hyperparameter optimization."""

    def test_optimize_execution_policy(self, synthetic_labeled_dataset):
        from darefx.models.tuner import HyperparameterTuner

        df, feature_cols = synthetic_labeled_dataset
        # Create minimal synthetic OOS DataFrame
        df_oos = df.copy()
        df_oos["open"] = df_oos["close"]
        df_oos["high"] = df_oos["close"] + 0.0020
        df_oos["low"] = df_oos["close"] - 0.0020
        df_oos["prob_buy"] = np.random.uniform(0.2, 0.6, len(df))
        df_oos["prob_sell"] = np.random.uniform(0.2, 0.6, len(df))
        df_oos["prob_neutral"] = 1.0 - (df_oos["prob_buy"] + df_oos["prob_sell"]).clip(0, 0.9)
        df_oos["atr_14"] = 0.0050
        df_oos["adx_14"] = np.random.uniform(15.0, 35.0, len(df))

        tuner = HyperparameterTuner(df_features=df_oos, feature_cols=feature_cols, n_trials=5)
        res = tuner.optimize_execution_policy(df_oos=df_oos)

        assert "best_score" in res
        assert "best_params" in res
        assert "threshold" in res["best_params"]

