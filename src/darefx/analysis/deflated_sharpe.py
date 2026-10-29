"""Deflated Sharpe Ratio (DSR) and Statistical Significance Suite.

Implements the institutional quantitative tests defined by
David H. Bailey and Marcos López de Prado (2014):
1. Probabilistic Sharpe Ratio (PSR) accounting for non-normal returns (skewness and kurtosis).
2. Deflated Sharpe Ratio (DSR) adjusting for multiple testing and selection bias.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from scipy import stats  # type: ignore


@dataclass(frozen=True)
class DSRResult:
    """Statistical significance evaluation result."""

    sharpe_ratio: float
    annualized_sharpe: float
    psr: float
    dsr: float
    expected_max_sharpe: float
    skewness: float
    kurtosis: float
    sample_size: int
    num_trials: int
    is_significant: bool  # True if DSR >= 0.95 (5% significance level)


def calculate_psr(
    returns: pd.Series | np.ndarray,
    benchmark_sr: float = 0.0,
    annualization_factor: float = 252.0,
) -> float:
    """Calculate the Probabilistic Sharpe Ratio (PSR).

    PSR measures the probability that the estimated Sharpe ratio is greater
    than a predetermined benchmark, correcting for fat tails (skewness and kurtosis).

    Formula (López de Prado, 2012):
        Z = ((SR - SR*) * sqrt(T - 1)) / sqrt(1 - skew * SR + ((kurt - 1) / 4) * SR^2)
        PSR = NormCDF(Z)
    """
    clean_returns = np.asarray(returns, dtype=np.float64)
    clean_returns = clean_returns[~np.isnan(clean_returns)]

    n = len(clean_returns)
    if n < 5:
        return 0.0

    mean_ret = float(np.mean(clean_returns))
    std_ret = float(np.std(clean_returns, ddof=1))

    if std_ret <= 1e-12:
        return 0.0

    # Unannualized period Sharpe ratio
    sr = mean_ret / std_ret

    skew = float(stats.skew(clean_returns))
    # stats.kurtosis calculates excess kurtosis by default; we need Pearson kurtosis (excess + 3)
    kurt = float(stats.kurtosis(clean_returns, fisher=False))

    variance_term = 1.0 - (skew * sr) + (((kurt - 1.0) / 4.0) * (sr**2))
    if variance_term <= 0.0:
        variance_term = 1e-6

    std_error = math.sqrt(variance_term / (n - 1.0))
    if std_error <= 1e-12:
        return 0.0

    z_score = (sr - benchmark_sr) / std_error
    psr = float(stats.norm.cdf(z_score))
    return psr


def calculate_expected_max_sharpe(
    num_trials: int,
    var_sharpe: float = 0.5,
    annualization_factor: float = 252.0,
) -> float:
    """Calculate the expected maximum Sharpe ratio under the null hypothesis.

    Approximates the Euler-Mascheroni threshold for selection bias under N independent trials.
    """
    if num_trials <= 1:
        return 0.0

    # Euler-Mascheroni constant
    euler_mascheroni = 0.57721566490153286

    term1 = (1.0 - euler_mascheroni) * stats.norm.ppf(1.0 - (1.0 / num_trials))
    term2 = euler_mascheroni * stats.norm.ppf(1.0 - (1.0 / (num_trials * math.e)))

    expected_max = math.sqrt(var_sharpe) * (term1 + term2)
    return max(0.0, float(expected_max))


def calculate_deflated_sharpe_ratio(
    returns: pd.Series | np.ndarray,
    num_trials: int = 35,
    var_sharpe: float = 0.25,
    annualization_factor: float = 252.0,
) -> DSRResult:
    """Calculate the Deflated Sharpe Ratio (DSR) adjusting for multiple testing.

    Parameters:
        returns: Daily portfolio trade returns series
        num_trials: Number of model configurations / Optuna trials explored
        var_sharpe: Variance of Sharpe ratios across all trials
        annualization_factor: 252 for daily bars
    """
    clean_returns = np.asarray(returns, dtype=np.float64)
    clean_returns = clean_returns[~np.isnan(clean_returns)]
    n = len(clean_returns)

    if n < 5:
        return DSRResult(
            sharpe_ratio=0.0,
            annualized_sharpe=0.0,
            psr=0.0,
            dsr=0.0,
            expected_max_sharpe=0.0,
            skewness=0.0,
            kurtosis=3.0,
            sample_size=n,
            num_trials=num_trials,
            is_significant=False,
        )

    mean_ret = float(np.mean(clean_returns))
    std_ret = float(np.std(clean_returns, ddof=1))

    period_sr = mean_ret / std_ret if std_ret > 1e-12 else 0.0
    annual_sr = period_sr * math.sqrt(annualization_factor)

    skew = float(stats.skew(clean_returns))
    kurt = float(stats.kurtosis(clean_returns, fisher=False))

    # Standard PSR against 0.0 benchmark
    psr = calculate_psr(clean_returns, benchmark_sr=0.0, annualization_factor=annualization_factor)

    # Expected max Sharpe ratio across N trials
    expected_max_sr = calculate_expected_max_sharpe(num_trials=num_trials, var_sharpe=var_sharpe)

    # Convert expected max annual SR to period SR for test comparison
    expected_max_period_sr = expected_max_sr / math.sqrt(annualization_factor)

    # DSR is PSR computed against the expected max threshold
    dsr = calculate_psr(clean_returns, benchmark_sr=expected_max_period_sr, annualization_factor=annualization_factor)

    return DSRResult(
        sharpe_ratio=period_sr,
        annualized_sharpe=annual_sr,
        psr=psr,
        dsr=dsr,
        expected_max_sharpe=expected_max_sr,
        skewness=skew,
        kurtosis=kurt,
        sample_size=n,
        num_trials=num_trials,
        is_significant=(dsr >= 0.95),
    )
