# DareFX

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![CI Workflow](https://img.shields.io/badge/tests-45%20passed-brightgreen.svg)](https://github.com/davinmaritza/darefx/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://github.com/davinmaritza/darefx/blob/main/LICENSE)
[![Quantitative Finance](https://img.shields.io/badge/quant-López%20de%20Prado-orange.svg)](https://github.com/davinmaritza/darefx/blob/main/docs/ARCHITECTURE.md)

**DareFX** is an institutional-grade, autonomous machine learning auto-trading engine engineered for daily swing trading on the EUR/USD forex currency pair.

The system combines supervised learning (LightGBM / XGBoost) with Marcos López de Prado's Triple Barrier Method, Purged Walk-Forward Cross-Validation, and Deflated Sharpe Ratio (DSR) statistical testing. Under the autonomous operating model, human intervention is strictly limited to broker deposits and capital allocation; DareFX autonomously executes 100% of data ingestion, feature extraction, inference, position sizing, order execution, and protective exits.

---

## Performance Summary (2007–2026 Out-of-Sample Walk-Forward)

Tested over 4,519 daily market bars under realistic execution friction (1.5 pips spread, 1.0 pip slippage, and $7.00/lot commission):

| Performance Metric | Backtest Value | Target Benchmark | Status |
| :--- | :--- | :--- | :--- |
| **Total Net Return** | **+30.31%** ($10k → $13,031.33) | > 0.00% | **PASS** |
| **Win Rate** | **57.14%** (84 wins / 63 losses) | > 50.00% | **PASS** |
| **Profit Factor** | **1.50** | > 1.30 | **PASS** |
| **Sharpe Ratio (Annualized)** | **2.95** | > 0.50 (Phase 3 Gate) | **PASS** |
| **Probabilistic Sharpe Ratio (PSR)** | **98.6%** | > 95.0% (5% Significance) | **PASS** |
| **Deflated Sharpe Ratio (DSR)** | **91.9%** | > 50.0% (35 optimization trials) | **PASS** |
| **Maximum Drawdown** | **5.96%** | < 15.00% (Hard limit) | **PASS** |
| **Trade Expectancy** | **+$20.62 per trade** | > $0.00 | **PASS** |
| **Formal Decision Verdict** | 🟢 **GO (LIVE CAPITAL READY)** | Statistical edge confirmed | **PASS** |

Full statistical audit report available in [`docs/EVALUATION-REPORT.md`](docs/EVALUATION-REPORT.md).

---

## Key Architectural Highlights

1. **Non-Lookahead Stationary Features**:
   - 35 features: RSI-14, MACD (12, 26, 9), Bollinger Bands, ATR-14, NATR, ADX-14, and EMA ratios (9, 21, 50, 200).
   - Rolling backward-looking Z-score normalization strictly anti-lookahead.
2. **Triple Barrier Labeling (López de Prado)**:
   - Dynamic profit target and stop loss barriers scaled by rolling ATR with vertical time-expiry barriers (5 daily bars).
3. **Purged Walk-Forward Cross-Validation (CPCV)**:
   - 79 walk-forward folds (36-month train, 6-month test, 3-month step) with 10-day purge gap and 5-day embargo to eliminate forward-looking overlap leakage.
4. **Layered Risk Management & Capital Protection**:
   - Fixed fractional position sizing (1.0% risk per trade) capped by half-Kelly criteria and 5.0% margin utilization ceiling.
   - Circuit Breaker state machine: `ACTIVE`, `PAUSED_DAILY` (-5.0% daily halt), and `SHUTDOWN` (-15.0% peak drawdown).
5. **Dual-Environment MetaTrader 5 Bridge**:
   - Native Linux paper trading / dry-run simulation mode.
   - Direct MT5 bridge adapter for execution against brokers (e.g. Valetax Demo / Live).
6. **Production Automations**:
   - Systemd service and timer unit files executing daily at 22:05 UTC (05:05 WIB) following New York 17:00 EST close.
   - Real-time Telegram Markdown alert dispatcher for signals, executions, closed trades, and circuit breaker events.

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/davinmaritza/darefx.git
cd darefx

# Setup Python 3.12 virtual environment using uv
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run test suite (45 unit & integration tests)
pytest -v
```

---

## CLI Usage

DareFX exposes a Typer-powered command line interface:

### 1. Ingest Market Data
```bash
# Download 25 years of daily EUR/USD bars into annual Parquet partitions
darefx fetch --source yahoo --symbol EURUSD --range-str 25y
```

### 2. Generate Features & Labels
```bash
darefx features --symbol EURUSD --pt 1.5 --sl 1.5 --holding 5
```

### 3. Train & Evaluate Models (Walk-Forward)
```bash
darefx train --symbol EURUSD --train-months 36 --test-months 6 --step-months 3
```

### 4. Run Out-of-Sample Backtest
```bash
darefx backtest --symbol EURUSD --threshold 0.46 --adx-min 32.0 --sl 1.0 --pt 1.2
```

### 5. Statistical Evaluation (DSR & Go/No-Go Decision)
```bash
darefx evaluate --symbol EURUSD --trials 35
```

### 6. Run Daily Autonomous Trading Cycle
```bash
# Simulation / Paper mode
darefx run-cycle --symbol EURUSD --equity 10000

# Live / Paper Execution via MT5 Bridge
darefx run-cycle --symbol EURUSD --equity 10000 --execute
```

### 7. Inspect Circuit Breaker Status
```bash
darefx risk-status
```

---

## Production Deployment

Refer to [`docs/DEPLOYMENT-RUNBOOK.md`](docs/DEPLOYMENT-RUNBOOK.md) for complete instructions on deploying DareFX as an unattended systemd user daemon on Linux Mint or a cloud VPS.

---

## Documentation Suite

Comprehensive technical documentation is maintained in [`docs/`](docs/):

- [`FOREX-101.md`](docs/FOREX-101.md) — Mechanics of forex, pips, leverage, and market session overlaps.
- [`PRD.md`](docs/PRD.md) — Product requirements and operational constraints.
- [`SRS.md`](docs/SRS.md) — Software requirements specification and data schemas.
- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) — System design and end-to-end component diagrams.
- [`DATA-PIPELINE.md`](docs/DATA-PIPELINE.md) — Ingestion, tick cleaning, resampling, and Parquet storage.
- [`RISK-MANAGEMENT.md`](docs/RISK-MANAGEMENT.md) — Position sizing, circuit breakers, and drawdowns.
- [`ROADMAP.md`](docs/ROADMAP.md) — Phased engineering milestone plan.
- [`EVALUATION-REPORT.md`](docs/EVALUATION-REPORT.md) — Formal Go/No-Go decision report and statistical audit.
- [`DEPLOYMENT-RUNBOOK.md`](docs/DEPLOYMENT-RUNBOOK.md) — Production operator deployment runbook.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
