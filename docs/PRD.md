# Product Requirements Document (PRD) — DareFX

## 1. Problem Statement

Manual forex trading suffers from emotional bias, cognitive fatigue, and execution inconsistency:
- Human traders make decisions based on fear, greed, and intuition rather than objective statistical expectancy.
- Traders exit winning positions prematurely out of fear, hold losing positions past predefined stop losses, and initiate revenge trades after sustaining drawdowns.
- The foreign exchange market operates 24 hours a day, 5 days a week. Human operators cannot continuously monitor price movements without physical exhaustion.
- Inconsistent trade sizing and discretionary rule violations deplete trading capital over time.

Supervised machine learning removes psychological interference. A systematic machine learning system computes statistical probabilities over historical price patterns, enforces position sizing rules deterministically, executes stop losses and take profits without hesitation, and operates continuously without operational fatigue.

## 2. Solution

DareFX is an autonomous supervised machine learning trading system designed for EUR/USD swing trading on the daily (D1) timeframe.

Core system capabilities:
- **Data Ingestion**: Ingests 10+ years of EUR/USD tick data from Dukascopy and recent daily bars from MetaTrader 5 (MT5).
- **Feature Engineering**: Computes technical indicators covering trend, momentum, and volatility (RSI, MACD, Bollinger Bands, ATR, ADX, EMAs).
- **Labeling**: Labels price paths using Marcos López de Prado's Triple Barrier Method with dynamic volatility boundaries.
- **Predictive Modeling**: Trains LightGBM and XGBoost gradient-boosted decision trees for directional classification.
- **Validation**: Prevents overfitting through Walk-Forward Validation with purging and embargo windows, supplemented by Combinatorial Purged Cross-Validation (CPCV).
- **Order Execution**: Connects to MT5 on Valetax to execute trades automatically at daily candle closes.
- **Risk Management**: Enforces fixed fractional risk (1.0% to 2.0%), half-Kelly criterion position scaling, and multi-tier circuit breakers (5% daily loss limit, 15% maximum drawdown limit).
- **Monitoring**: Transmits real-time execution alerts, daily balance summaries, and equity curve charts via Telegram.

## 3. User Persona

- **Profile**: Single user. Senior machine learning engineer and Python developer.
- **Forex Experience**: Zero live trading experience. Understands statistical modeling, loss functions, classification metrics, validation schemes, and leakage risks.
- **Workstation**: Linux Mint desktop (x86_64 architecture) running Python 3.12+.
- **Capital & Budget**: $0 initial financial outlay. No paid market data subscriptions, no commercial backtesting platforms, and no paid cloud infrastructure during development.
- **Primary Objective**: Build a reproducible, quantitative trading system that achieves positive risk-adjusted returns on a demo account before risking personal capital.

## 4. Use Cases

### UC1: Download and Store Historical EUR/USD Data
- **Description**: The user downloads historical tick data from Dukascopy, decompresses archives, aggregates ticks into daily OHLCV bars, and stores them in compressed Parquet format.
- **Preconditions**: Internet access is active; target storage directory exists.
- **Primary Flow**:
  1. User runs `darefx data download --source dukascopy --start 2014-01-01 --end 2024-12-31`.
  2. System downloads raw LZMA-compressed `.bi5` tick files from Dukascopy servers.
  3. System decompresses ticks (timestamp, bid price, ask price, bid volume, ask volume).
  4. System aggregates ticks into daily OHLCV bars using bid prices (Open: first bid, High: max bid, Low: min bid, Close: last bid, Volume: sum of tick volumes).
  5. System verifies schema integrity and checks for missing timestamps.
  6. System saves daily bars to `data/processed/eurusd_d1.parquet`.
- **Postconditions**: Validated 10+ year daily OHLCV dataset stored on disk.

### UC2: Compute Technical Indicator Features
- **Description**: The system computes trend, momentum, and volatility indicators on daily OHLCV data to construct the modeling feature matrix.
- **Preconditions**: `data/processed/eurusd_d1.parquet` exists and passes schema validation.
- **Primary Flow**:
  1. User runs `darefx features compute`.
  2. System loads daily OHLCV bars.
  3. System calculates technical indicators: RSI-14, MACD (12, 26, 9), Bollinger Bands (20, 2), ATR-14, ADX-14, EMA-9, EMA-21, EMA-50, and EMA-200.
  4. System generates derived features: price distance to EMAs, EMA slopes, and ATR normalized by close price.
  5. System drops the initial 200 warm-up bars to eliminate NaN values.
  6. System saves feature matrix to `data/features/features_d1.parquet`.
- **Postconditions**: Complete feature matrix stored without missing values.

### UC3: Label Data with Triple Barrier Method
- **Description**: The system assigns directional labels to each bar using Marcos López de Prado's Triple Barrier Method.
- **Preconditions**: Feature matrix and OHLCV price series exist.
- **Primary Flow**:
  1. User runs `darefx labels create --pt 2.0 --sl 1.0 --holding 5`.
  2. System reads closing prices and ATR-14 values.
  3. System computes dynamic barriers for each bar: upper profit barrier at $+2.0 \times \text{ATR}$, lower stop barrier at $-1.0 \times \text{ATR}$, and vertical time barrier at 5 trading days.
  4. System evaluates future price action:
     - Assigns `+1` (Buy) if price touches upper barrier first.
     - Assigns `-1` (Sell) if price touches lower barrier first.
     - Assigns `0` (Neutral) if vertical time barrier expires before either horizontal barrier is touched.
  5. System calculates sample uniqueness weights to correct for overlapping holding periods.
  6. System writes labeled dataset to `data/features/labeled_dataset.parquet`.
- **Postconditions**: Dataset containing features, target labels, and sample weights stored on disk.

### UC4: Train and Evaluate ML Model
- **Description**: The user trains LightGBM or XGBoost classification models using walk-forward validation and Combinatorial Purged Cross-Validation (CPCV).
- **Preconditions**: `data/features/labeled_dataset.parquet` exists.
- **Primary Flow**:
  1. User runs `darefx model train --model lightgbm --validate walk-forward`.
  2. System partitions data into rolling walk-forward train and test splits, applying purging and embargo periods.
  3. System optimizes hyperparameters with Optuna over 100 trials if hyperparameter tuning is requested.
  4. System fits LightGBM or XGBoost on training splits using sample uniqueness weights.
  5. System computes out-of-sample metrics: log-loss, accuracy, precision, recall, and F1-score across splits.
  6. System serializes the trained model and writes metadata (hyperparameters, training date ranges, performance metrics) to `data/models/<model_id>/`.
- **Postconditions**: Trained model artifact and evaluation report saved to disk.

### UC5: Backtest Strategy with Realistic Costs
- **Description**: The system runs a historical backtest of model signals, applying spread, commission, and slippage fees.
- **Preconditions**: Trained model artifact and historical feature dataset exist.
- **Primary Flow**:
  1. User runs `darefx backtest run --model-id <model_id> --spread-pips 1.2 --commission-per-lot 7.0 --slippage-pips 0.2`.
  2. System iterates through out-of-sample bars chronologically.
  3. System applies model predictions at daily bar close and plans execution for the next bar open.
  4. System computes position sizes using fixed fractional risk and half-Kelly scaling.
  5. System tracks trade exits against triple barrier thresholds, deducting spread, commission, and slippage costs.
  6. System evaluates daily drawdown limits and updates circuit breaker state.
  7. System computes Sharpe ratio, Sortino ratio, Calmar ratio, maximum drawdown, win rate, and profit factor.
  8. System saves trade log CSV and equity curve plot to `data/backtests/`.
- **Postconditions**: Backtest performance report and trade log generated.

### UC6: Paper Trade on Demo Account
- **Description**: The bot runs autonomously against a Valetax MetaTrader 5 demo account, generating signals at daily bar close and placing orders.
- **Preconditions**: Validated model registered; MT5 demo account credentials configured in `.env`.
- **Primary Flow**:
  1. User executes `darefx trade paper`.
  2. System initializes connection to MT5 terminal.
  3. At 22:00 UTC (daily candle close), system fetches the latest completed D1 bar.
  4. System updates technical indicators and constructs the feature vector.
  5. System generates prediction probabilities from the active model.
  6. If signal confidence exceeds threshold (e.g., probability > 0.55), system queries current equity and computes lot size.
  7. System sends a market order (`TRADE_ACTION_DEAL`) with predefined Stop Loss and Take Profit levels via MT5 API.
  8. System records the trade in local SQLite database and dispatches a trade execution alert to Telegram.
- **Postconditions**: Live demo order active with attached Stop Loss and Take Profit; trade recorded in local database.

### UC7: Monitor Trades and P&L via Telegram
- **Description**: The system delivers operational alerts, trade execution logs, and daily performance summaries to the user's Telegram client.
- **Preconditions**: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` configured in `.env`.
- **Primary Flow**:
  1. System detects trade event (order open, stop loss exit, take profit exit, or time exit).
  2. System constructs formatted message detailing ticket number, direction, entry price, exit price, pip outcome, and USD P&L.
  3. System sends message via Telegram Bot API.
  4. At 00:00 UTC daily, system compiles 24-hour summary (account balance, equity, open positions, daily net return) and sends equity curve image.
- **Postconditions**: Real-time operational logs and visual reports delivered to the user.

### UC8: Auto-Pause and Shutdown on Excessive Drawdown
- **Description**: The system triggers automated risk circuit breakers when account drawdown crosses predefined risk thresholds.
- **Preconditions**: Paper or live trade execution loop is active.
- **Primary Flow**:
  1. System recalculates daily drawdown and cumulative peak-to-trough drawdown after every bar close or position update.
  2. If daily drawdown reaches or exceeds 5.0%, system closes all open positions and enters `SOFT_PAUSE` state, blocking new trades for 24 hours.
  3. If cumulative drawdown reaches or exceeds 15.0%, system closes all open positions and enters `HARD_HALT` state, halting all bot operations.
  4. System dispatches an emergency notification to Telegram detailing drawdown levels and liquidation actions.
  5. System persists the halt state to disk; resuming trading requires manual operator intervention via `darefx resume --force`.
- **Postconditions**: Trading suspended; open positions liquidated; capital preserved.

### UC9: Graduate to Live Trading with Micro-Lots
- **Description**: The user switches the system from demo execution to live capital trading using minimum position sizes after completing validation criteria.
- **Preconditions**: Minimum 3 continuous months of paper trading completed; out-of-sample Sharpe > 1.0; maximum drawdown < 15.0%; win rate within +/-5.0% of backtest results.
- **Primary Flow**:
  1. User updates `.env` with live Valetax MT5 account credentials.
  2. User runs `darefx trade live --micro-lots`.
  3. System enforces strict live guardrails: risk per trade capped at 0.5%, position sizes locked to 0.01 lots (micro-lot).
  4. System executes daily trading loop with identical indicator calculation, signal generation, and circuit breaker logic.
  5. System records execution slippage and spread differentials against paper trading baselines.
- **Postconditions**: Live micro-lot trades executed under strict risk constraints.

## 5. Success Metrics

| Metric | Target | Evaluation Method | Rationale |
|---|---|---|---|
| **Sharpe Ratio** | > 1.0 | 5-year out-of-sample backtest & 3-month paper test | Confirms acceptable risk-adjusted returns relative to portfolio volatility. |
| **Maximum Drawdown** | < 20.0% | Entire out-of-sample backtest & paper test | Prevents severe capital impairment and preserves trading account balance. |
| **Annualized Return** | > 10.0% | Out-of-sample backtest and annualized paper return | Exceeds the historical average annual return of the S&P500 benchmark. |
| **Win Rate Consistency** | Within +/-5.0% of backtest | 3-month forward paper test compared to backtest | Validates that live execution matches backtest distribution without model degradation. |
| **Paper Trading Duration** | Minimum 3 continuous months | Uninterrupted forward testing on MT5 demo | Proves system stability across multiple market regimes before committing real funds. |
| **Profit Factor** | > 1.3 | Out-of-sample backtest | Confirms gross profits exceed gross losses by a sufficient margin to absorb slippage and spreads. |
| **Calmar Ratio** | > 0.6 | Out-of-sample backtest | Confirms annualized return justifies historical maximum drawdown risk. |
| **Signal Latency** | < 5 minutes | Daily bar close processing window | Ensures timely order placement at the open of the subsequent daily bar (22:00 UTC). |

## 6. Non-Goals

- **High-Frequency Trading (HFT) and Scalping**: DareFX operates exclusively on the daily (D1) timeframe. The system will not process sub-minute data, tick-level order queues, or latency arbitrage.
- **Multi-Pair Trading**: Version 1 trades EUR/USD exclusively. Cross-currency pairs, exotic currencies, and currency baskets are out of scope.
- **Multi-Asset Trading**: The system does not support equities, fixed income, cryptocurrencies, options, futures, or commodity contracts.
- **SaaS or Multi-Tenant Platform**: DareFX is a single-user system deployed locally. Multi-user authentication, cloud multi-tenancy, and client portals are out of scope.
- **Social and Copy Trading**: The system does not provide signal broadcasting, webhooks for external copiers, or social leaderboards.
- **Mobile Application**: The system does not include native iOS or Android apps. Telegram handles all mobile notifications and status reports.
- **Paid API Dependencies**: The core system will not depend on paid financial data subscriptions (e.g., Bloomberg, Refinitiv, TradingView) or commercial execution tools.

## 7. Constraints

- **Financial Budget**: $0 capital expenditure. All development tools, libraries, historical data sources (Dukascopy), and broker connections (Valetax MT5 demo) must be free.
- **Operating System and Platform**: Development runs on Linux Mint. The official MetaTrader 5 Python client library requires Windows. During Phases 1 through 3, all data ingestion, feature engineering, model training, and backtesting run natively on Linux Mint. MT5 broker execution in Phase 4 requires running MT5 via Wine, a virtual machine, or a dedicated Windows environment.
- **Broker**: Valetax MetaTrader 5 demo environment. System models EUR/USD contract mechanics (100,000 unit standard lot, 5-decimal pricing, broker spreads, and overnight swap rates).
- **Timeline**: 3 to 6 months from initial architecture design to functional paper trading MVP.
