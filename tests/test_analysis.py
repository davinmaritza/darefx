"""Tests for DareFX Analysis Suite: Deflated Sharpe Ratio, Reconciliation, and Evaluator."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from darefx.analysis.deflated_sharpe import (
    calculate_deflated_sharpe_ratio,
    calculate_expected_max_sharpe,
    calculate_psr,
)
from darefx.analysis.evaluator import DecisionRecommendation, SystemEvaluator
from darefx.analysis.reconciler import reconcile_trades


class TestDeflatedSharpe:
    """Test suite for DSR, PSR, and multiple-testing bias adjustments."""

    def test_psr_winning_strategy(self) -> None:
        np.random.seed(42)
        # 100 positive-drift returns
        returns = np.random.normal(loc=0.002, scale=0.01, size=150)
        psr = calculate_psr(returns, benchmark_sr=0.0)

        assert 0.90 <= psr <= 1.0

    def test_psr_empty_or_zero_variance(self) -> None:
        assert calculate_psr(np.array([])) == 0.0
        assert calculate_psr(np.array([0.01, 0.01, 0.01])) == 0.0

    def test_expected_max_sharpe_growth_with_trials(self) -> None:
        max_10 = calculate_expected_max_sharpe(num_trials=10, var_sharpe=0.5)
        max_100 = calculate_expected_max_sharpe(num_trials=100, var_sharpe=0.5)

        assert max_10 > 0.0
        assert max_100 > max_10

    def test_deflated_sharpe_ratio_structure(self) -> None:
        np.random.seed(42)
        returns = np.random.normal(loc=0.0015, scale=0.008, size=200)
        dsr_res = calculate_deflated_sharpe_ratio(returns=returns, num_trials=30)

        assert dsr_res.sample_size == 200
        assert dsr_res.num_trials == 30
        assert dsr_res.psr >= 0.0
        assert dsr_res.dsr >= 0.0
        assert isinstance(dsr_res.is_significant, bool)


class TestReconciler:
    """Test suite for trade reconciliation and empirical slippage."""

    def test_reconcile_trades_perfect_match(self) -> None:
        th = pd.DataFrame([
            {"action": "BUY", "entry_price": 1.08500, "pnl": 150.0},
            {"action": "SELL", "entry_price": 1.09200, "pnl": -50.0},
        ])
        ex = pd.DataFrame([
            {"action": "BUY", "open_price": 1.08505, "pnl": 145.0},   # 0.5 pip slippage
            {"action": "SELL", "open_price": 1.09195, "pnl": -55.0},  # 0.5 pip slippage
        ])

        report = reconcile_trades(th, ex, max_slippage_threshold_pips=1.0)
        assert report.total_theoretical_signals == 2
        assert report.total_executed_trades == 2
        assert report.match_rate_pct == 100.0
        assert not report.slippage.violates_assumption
        assert pytest.approx(report.slippage.mean_slippage_pips, abs=0.01) == 0.5

    def test_reconcile_trades_empty(self) -> None:
        report = reconcile_trades(pd.DataFrame(), pd.DataFrame())
        assert report.total_theoretical_signals == 0
        assert report.total_executed_trades == 0
        assert len(report.discrepancies) > 0


class TestSystemEvaluator:
    """Test suite for end-to-end evaluation and report generation."""

    def test_evaluator_produces_report(self, tmp_path: Path) -> None:
        trades = pd.DataFrame([
            {"action": "BUY", "entry_price": 1.0800, "exit_price": 1.0920, "pnl": 120.0, "pnl_pct": 0.012, "holding_bars": 3},
            {"action": "SELL", "entry_price": 1.0900, "exit_price": 1.0820, "pnl": 80.0, "pnl_pct": 0.008, "holding_bars": 2},
            {"action": "BUY", "entry_price": 1.0850, "exit_price": 1.0810, "pnl": -40.0, "pnl_pct": -0.004, "holding_bars": 1},
            {"action": "SELL", "entry_price": 1.0830, "exit_price": 1.0770, "pnl": 60.0, "pnl_pct": 0.006, "holding_bars": 4},
            {"action": "BUY", "entry_price": 1.0790, "exit_price": 1.0890, "pnl": 100.0, "pnl_pct": 0.010, "holding_bars": 5},
        ])

        evaluator = SystemEvaluator()
        outcome = evaluator.evaluate(trades_df=trades, initial_capital=10_000.0)

        assert outcome.recommendation in (DecisionRecommendation.GO, DecisionRecommendation.ITERATE)
        assert outcome.confidence_pct > 0.0

        report_file = tmp_path / "EVALUATION-REPORT.md"
        content = evaluator.generate_report_markdown(outcome, output_file=report_file)

        assert report_file.exists()
        assert "DareFX — Formal System Evaluation and Go/No-Go Decision Report" in content
        assert "Performance Metric" in content


class TestMarketAnalyzer:
    """Test suite for AI Market Analyzer and automated Buy/Sell diagnosis."""

    def test_market_analyzer_generates_valid_report(self) -> None:
        from darefx.analysis.market_analyzer import MarketAnalysisReport, MarketAnalyzer

        analyzer = MarketAnalyzer(symbol="EURUSD")
        report = analyzer.analyze(account_equity=10_000.0, fetch_live=False)

        assert isinstance(report, MarketAnalysisReport)
        assert report.symbol == "EURUSD"
        assert report.current_price > 0.5
        assert report.adx_14 >= 0.0
        assert 0.0 <= report.rsi_14 <= 100.0
        assert report.atr_pips > 0.0
        assert report.recommendation in ("BUY", "SELL", "WAIT & SEE")
        assert 0.0 <= report.prob_buy <= 1.0
        assert 0.0 <= report.prob_sell <= 1.0
        assert 0.0 <= report.prob_neutral <= 1.0
        assert report.recommended_lots >= 0.01

        # Check serialization and markdown rendering
        data = report.to_dict()
        assert data["symbol"] == "EURUSD"
        assert "recommendation" in data
        assert "current_price" in data

        md = report.to_telegram_markdown()
        assert "ANALISIS AI PASAR & REKOMENDASI TRADING" in md
        assert "DIAGNOSIS TEKNIKAL & REGIME" in md
        assert "PROBABILITAS MODEL AI (LIGHTGBM)" in md

    def test_telegram_server_routes_analysis_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import MagicMock
        from darefx.notifications.telegram_server import TelegramServer

        server = TelegramServer(bot_token="test_token", chat_id="123456")
        sent_messages = []

        def mock_post(url: str, json: dict, timeout: int) -> MagicMock:
            resp = MagicMock()
            resp.status_code = 200
            sent_messages.append(json)
            return resp

        import requests
        monkeypatch.setattr(requests, "post", mock_post)

        # Route /analisis
        server.handle_message("/analisis", 123456)
        assert len(sent_messages) >= 2  # loading message + final report
        assert any("Mengambil data live" in m.get("text", "") for m in sent_messages)
        assert any("ANALISIS AI PASAR" in m.get("text", "") for m in sent_messages)

