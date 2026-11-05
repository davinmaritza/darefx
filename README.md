<p align="center">
  <img src="assets/logo/darefx-logo-horizontal.png" alt="DareFX Quantitative Trading Station" width="720"/>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12-blue.svg" alt="Python 3.12"/></a>
  <a href="https://github.com/davinmaritza/darefx/actions"><img src="https://img.shields.io/badge/tests-75%20passed-brightgreen.svg" alt="Tests 75 Passed"/></a>
  <a href="https://github.com/davinmaritza/darefx/releases"><img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="Version 1.0.0"/></a>
  <a href="https://github.com/davinmaritza/darefx/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License MIT"/></a>
</p>

**DareFX** is an automated trading terminal and daily swing execution system for EUR/USD. It combines supervised machine learning models with volatility-based barrier exits and automated position management over MetaTrader 5.

The system runs daily after the New York close (17:00 EST / 22:00 UTC), generates directional predictions using walk-forward trained LightGBM models, calculates fixed-risk position sizes, and executes orders directly via MetaTrader 5 with active break-even trailing protection.

---

## Downloads & Installers

Standalone desktop binaries and installers are available directly from [**GitHub Releases**](https://github.com/davinmaritza/darefx/releases/tag/v1.0.0):

| Platform | Format | Download Link | Size | Details |
| :--- | :--- | :--- | :--- | :--- |
| Windows (x86_64) | `.exe` | [DareFX-windows-x86_64.exe](https://github.com/davinmaritza/darefx/releases/download/v1.0.0/DareFX-windows-x86_64.exe) | 186 MB | Portable executable with native MetaTrader 5 API integration |
| Linux (Debian / Ubuntu / Mint) | `.deb` | [darefx_1.0.0_amd64.deb](https://github.com/davinmaritza/darefx/releases/download/v1.0.0/darefx_1.0.0_amd64.deb) | 526 MB | Standard Debian package with desktop launcher and app menu entry |
| Linux (Generic x86_64) | `.tar.gz` | [DareFX-linux-x86_64.tar.gz](https://github.com/davinmaritza/darefx/releases/download/v1.0.0/DareFX-linux-x86_64.tar.gz) | 534 MB | Self-contained binary archive |

### Running the Pre-built Binaries

```bash
# Windows
# Download DareFX-windows-x86_64.exe and double-click to launch

# Linux (Debian / Ubuntu / Linux Mint)
sudo dpkg -i darefx_1.0.0_amd64.deb
darefx-gui

# Linux (Portable Archive)
tar -xzf DareFX-linux-x86_64.tar.gz
./DareFX
```

---

## Desktop Terminal

The desktop client (`app.py`) is built with PySide6 / Qt and connects directly to the local or remote MT5 bridge:

- Balance, equity, margin, and floating PnL summary cards
- Active position table with live pip tracking, break-even status indicators, and individual close buttons
- Controls for auto-trading, panic close, manual order entry, and on-demand model inference
- System tray integration for background monitoring without interrupting open trades

```bash
# Launch GUI from source
python app.py

# Or on Windows using the batch launcher
run_gui.bat
```

---

## How It Works

- **Feature pipeline**: Computes 35 stationary indicators (RSI-14, MACD, Bollinger Bands, ATR-14, NATR, ADX-14, EMA ratios) normalized with rolling backward-looking z-scores to prevent data leakage.
- **Labeling and exits**: Uses triple-barrier labeling where profit targets and stop losses scale with rolling ATR, alongside a 5-day maximum holding period.
- **Validation**: Walk-forward cross-validation across 79 folds (36 months train, 6 months test, 3 months step) with a 10-day purge gap and 5-day embargo to eliminate overlap bias.
- **Risk controls**: Fixed fractional position sizing (1.0% equity risk per trade) capped by half-Kelly constraints, automatic break-even adjustment (+1.5 pips profit lock once price advances +15 pips), and circuit breakers for daily drawdown limits.
- **MetaTrader 5 bridge**: Connects directly on Windows to the MT5 terminal API, or remotely from Linux through a secure local bridge tunnel.

```
Market Data (Daily OHLCV)
   │
   ▼
Feature Pipeline (35 Indicators, Rolling Z-Score)
   │
   ▼
LightGBM Walk-Forward Inference ──► ADX Trend Filter (ADX >= 32.0)
   │
   ▼
Position Sizer (1% Risk / Half-Kelly)
   │
   ▼
MT5 Execution Bridge ──► Break-Even Trailing Guard (+1.5 pips lock)
```

---

## Backtest & Validation Results (2007–2026)

Evaluated across 4,519 daily bars under realistic transaction friction (1.5 pips spread, 1.0 pip slippage, and $7.00/lot commission):

| Metric | Result | Benchmark | Status |
| :--- | :--- | :--- | :--- |
| Total Net Return | +37.58% ($10k → $13,757) | > 0.00% | Pass |
| Win Rate | 59.02% (72 wins / 50 losses) | > 50.00% | Pass |
| Profit Factor | 1.72 | > 1.30 | Pass |
| Annualized Sharpe Ratio | 4.24 | > 0.50 | Pass |
| Probabilistic Sharpe Ratio (PSR) | 99.7% | > 95.0% | Pass |
| Deflated Sharpe Ratio (DSR) | 98.2% (35 trials) | > 50.0% | Pass |
| Maximum Drawdown | 4.62% | < 15.00% | Pass |
| Trade Expectancy | +$30.80 / trade | > $0.00 | Pass |

Full evaluation details are available in [`docs/EVALUATION-REPORT.md`](docs/EVALUATION-REPORT.md).

---

## Quick Start (from Source)

### Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- MetaTrader 5 terminal (for live execution)

### Installation

```bash
# Clone the repository
git clone https://github.com/davinmaritza/darefx.git
cd darefx

# Set up virtual environment and install dependencies
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run test suite
pytest -v
```

---

## CLI Reference

DareFX provides a command-line interface for the data pipeline, training, and execution:

### 1. Ingest Market Data
```bash
# Fetch daily EUR/USD bars into annual Parquet partitions
darefx fetch --source yahoo --symbol EURUSD --range-str 25y
```

### 2. Generate Features and Labels
```bash
darefx features --symbol EURUSD --pt 1.5 --sl 1.5 --holding 5
```

### 3. Train Models (Walk-Forward)
```bash
darefx train --symbol EURUSD --train-months 36 --test-months 6 --step-months 3
```

### 4. Run Backtest
```bash
darefx backtest --symbol EURUSD --threshold 0.46 --adx-min 32.0 --sl 1.0 --pt 1.2
```

### 5. Run Statistical Significance Audit (DSR)
```bash
darefx evaluate --symbol EURUSD --trials 35
```

### 6. Run Daily Trading Cycle
```bash
# Simulation / Dry-run
darefx run-cycle --symbol EURUSD --equity 10000

# Live execution via MT5 Bridge
darefx run-cycle --symbol EURUSD --equity 10000 --execute
```

### 7. Check Risk & Circuit Breaker Status
```bash
darefx risk-status
```

---

## Documentation

- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Component architecture and data flow diagrams
- [`RISK-MANAGEMENT.md`](docs/RISK-MANAGEMENT.md) — Sizing models, break-even mechanics, and drawdown limits
- [`DATA-PIPELINE.md`](docs/DATA-PIPELINE.md) — Ingestion, tick cleaning, resampling, and Parquet storage
- [`DEPLOYMENT-RUNBOOK.md`](docs/DEPLOYMENT-RUNBOOK.md) — Systemd service and production deployment guide
- [`EVALUATION-REPORT.md`](docs/EVALUATION-REPORT.md) — Out-of-sample backtest report and statistical audit

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
