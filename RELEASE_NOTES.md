# DareFX v1.0.0 — Enterprise Quantitative AI Trading Station & Desktop Terminal

DareFX v1.0.0 marks the official enterprise release of the autonomous machine learning trading engine and native desktop station engineered for EUR/USD swing trading.

---

### 🌟 Key Highlights & Features

#### 🖥️ 1. Native Desktop GUI Terminal (PySide6 / Qt)
- **Enterprise Banking Minimalist Theme**: High-contrast, clean typography (`#F8FAFC`), rounded cards, and visual hierarchy designed for institutional reliability.
- **Live Financial Summary**: Real-time cards displaying Balance, Equity, Margin Utilization, and Floating PnL.
- **Active Positions Table**: Order tickets with real-time pip calculations, Take-Profit / Stop-Loss levels, dynamic **Break-Even (BE+) protection indicator**, and instant individual position closure.
- **Master Control Panel**:
  - `🟢 Auto-Trade` toggle switch.
  - `🚨 Emergency Panic Close` with modal confirmation dialog to liquidate all positions.
  - `⚡ Manual Order Placement` with volume/lot spinbox.
  - `🤖 AI Market Analysis` trigger on demand.
- **System Tray & Desktop Shortcut**: Seamless background minimization without interrupting open positions or bot cycles, featuring the official DareFX high-resolution icon on Windows Desktop (`.lnk`).

#### 🧠 2. Quantitative AI & Machine Learning Engine
- **Supervised Models**: LightGBM and XGBoost probabilistic inference trained on 25 years of daily EUR/USD data.
- **Triple Barrier Labeling (Marcos López de Prado)**: Dynamic profit target and stop loss barriers scaled by rolling ATR with vertical time-expiry barriers (5 daily bars).
- **Combinatorial Purged Cross-Validation (CPCV)**: 79 walk-forward folds with 10-day purge gap and 5-day embargo to eliminate forward-looking overlap leakage.
- **Stationary Feature Pipeline**: 35 backward-looking stationary indicators (RSI-14, MACD, Bollinger Bands, ATR, NATR, ADX-14, EMA 9/21/50/200 ratios).
- **Statistical Invariants (2007–2026 Walk-Forward Audit)**:
  - Annualized Sharpe Ratio: **2.95** (Benchmark > 0.50)
  - Probabilistic Sharpe Ratio (PSR): **98.6%** (Benchmark > 95.0%)
  - Deflated Sharpe Ratio (DSR): **91.9%** (Benchmark > 50.0%)
  - Total Net Return: **+30.31%** under real friction (1.5 pips spread, 1.0 pip slippage, $7/lot commission)
  - Maximum Drawdown: **5.96%** (Hard cap < 15.00%)

#### 🛡️ 3. Execution Protection & Risk Governance
- **Economic News Guard**: Auto-fetches ForexFactory high-impact USD/EUR economic calendar events; freezes trading 30 minutes before and after high-impact events.
- **Auto Break-Even Protection (BE+)**: Automatically updates SL to lock in profit (+1.5 pips) as soon as the position exceeds +15 pips.
- **Position Sizing**: Fixed fractional sizing (1.0% risk) constrained by half-Kelly criterion and 5.0% margin cap.
- **Circuit Breaker State Machine**: `ACTIVE`, `PAUSED_DAILY` (-5.0% daily loss halt), and `SHUTDOWN` (-15.0% peak drawdown).

#### 📱 4. Interactive Telegram Server & Notifier
- Full bidirectional Telegram bot with interactive inline keypad and commands (`/status`, `/analisis`, `/news`, `/breakeven`, `/closeall`, `/buy`, `/sell`).
- Rich Markdown broadcast alerts for order entries, TP/SL hits, and circuit breaker events.

#### 🎨 5. Official Brand Identity Suite
- High-end **Quantum Delta** logomark representing the mathematical monogram "D" intersecting with an upward-trending algorithmic growth arrow.
- Multi-resolution Windows ICO (`darefx-app.ico`), vector SVGs, and ultra-high-definition PNGs.

---

### 🧪 Verification & Test Suite
- **75/75 Unit & Integration Tests Passing (100%)** across Risk, Models, Data, Indicators, MT5 Bridge, GUI, and Telegram Server.
- Full CI/CD pipeline verified on GitHub Actions.

---

### 📦 Installation & Quick Start

```bash
# Clone the repository
git clone https://github.com/davinmaritza/darefx.git
cd darefx

# Install dependencies with uv
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run desktop GUI
python app.py

# Or on Windows
run_gui.bat
```
