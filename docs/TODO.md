# DareFX — Task Checklist

Master implementation checklist for the DareFX EUR/USD automated trading system.

## Phase 1: Foundation (Month 1)

### Forex Mechanics & Broker Setup
- [ ] Read `docs/FOREX-101.md` covering currency pairs, pips, lots, margin calculations, and order execution types
- [ ] Open Valetax demo trading account with MT5 server credentials and 1:100 margin ratio
- [ ] Place 10 manual demo orders in MT5 terminal testing market execution, buy limit, sell stop, stop-loss, and take-profit mechanics
- [ ] Log bid-ask spread variations across Asian, London, and New York market sessions

### Data Ingestion Pipeline
- [x] Research Dukascopy bi5 tick data file format and hourly URL directory structure
- [x] Implement HTTP downloader with retry logic and rate limiting in `src/darefx/data/downloader.py`
- [x] Implement LZMA decompression for downloaded binary `.bi5` payload files
- [x] Implement binary data unpacker extracting millisecond offsets, ask prices, bid prices, and volume floats
- [x] Implement secondary data fetcher (Yahoo Finance unblocked 25-year provider) as robust ISP-resilient source
- [x] Write unit tests for downloader verifying download retries, caching, and error recovery

### Data Processing & Cleaning
- [x] Implement tick-to-daily OHLCV resampler using the 17:00 New York EST close standard in `src/darefx/data/preprocessor.py`
- [x] Filter weekend ticks and normalize timestamps to UTC
- [x] Flag price anomalies, non-positive prices, and zero-spread records in `src/darefx/data/preprocessor.py`
- [x] Write unit tests verifying OHLC consistency: high >= max(open, close) and low <= min(open, close)

### Storage & Data Validation
- [x] Implement Parquet export engine with annual partitioning in `src/darefx/data/storage.py`
- [x] Write schema enforcement check verifying datatypes (UTC timestamp, float64 OHLC, float64 volume)
- [x] Write data integrity tests in `tests/test_data.py` verifying zero NaN values and monotonic chronological ordering
- [x] Benchmark Parquet read performance to verify 20+ years of daily data loads into memory in under 2 seconds

### Exploratory Data Analysis
- [x] Create Jupyter notebook `notebooks/01_data_exploration.ipynb`
- [x] Plot 2003–present EUR/USD daily price history with structural event markers (2008 GFC, 2015 SNB unpeg, 2020 COVID)
- [x] Compute and plot daily logarithmic return distribution against Gaussian reference curve
- [x] Calculate rolling 21-day, 63-day, and 252-day annualized volatility series
- [x] Calculate Autocorrelation (ACF) and Partial Autocorrelation (PACF) for raw returns and absolute returns

---

## Phase 2: Feature Engineering + First Model (Month 2)

### Technical Indicator Engineering
- [x] Implement momentum indicators in `src/darefx/features/technical.py`: RSI (14), Stochastic (14, 3), and MACD (12, 26, 9)
- [x] Implement trend and volatility indicators: Bollinger Bands (20, 2), ATR (14), NATR, and ADX (14)
- [x] Implement moving averages (EMA 9, 21, 50, 200) and moving average distance ratios
- [x] Write unit tests for all indicators verifying calculation accuracy and boundary invariants in `tests/test_features.py`

### Feature Scaling & Pipeline
- [x] Implement rolling z-score normalizer with backward-looking window to prevent look-ahead bias in `src/darefx/features/technical.py`
- [x] Implement feature assembly pipeline combining indicators into clean tabular matrices in `src/darefx/features/pipeline.py`
- [x] Write leakage verification test checking that timestamp T features contain zero information from timestamp T+1

### Triple Barrier Labeling
- [x] Implement triple barrier labeling algorithm in `src/darefx/features/labels.py`
- [x] Configure dynamic horizontal barriers using ATR volatility multipliers (1.5 * ATR for profit target and stop loss)
- [x] Configure vertical barrier enforcing maximum trade holding duration of 5 daily bars
- [x] Map barrier touches to discrete classification targets (+1 profit, -1 stop loss, 0 time exit) and verify class balance

### Validation Architecture
- [x] Implement walk-forward split generator supporting expanding and rolling windows in `src/darefx/models/validator.py`
- [x] Configure standard walk-forward parameters: 36-month training window, 6-month validation window, 3-month step
- [x] Implement purge and embargo window buffers to eliminate serial correlation and barrier overlap leakage

### Baseline LightGBM Model & Backtest
- [x] Implement LightGBM classification trainer with multi-class log loss in `src/darefx/models/trainer.py`
- [x] Train baseline LightGBM model across walk-forward folds using default parameters
- [x] Calculate feature importance across out-of-sample splits and rank by gain
- [x] Build event-driven execution engine in `src/darefx/backtest/engine.py` applying 1.5 pip round-trip spread cost and slippage
- [x] Generate baseline backtest performance summary containing returns, Sharpe ratio, and maximum drawdown via `darefx backtest`

---

## Phase 3: Model Iteration & Realistic Backtesting (Month 3)

### Advanced Cross-Validation
- [ ] Implement Combinatorial Purged Cross-Validation (CPCV) generator in `src/darefx/models/cpcv.py`
- [ ] Implement combinatorial backtest path reconstruction to generate distributions of Sharpe ratios
- [ ] Write unit tests checking that CPCV purge gaps clear all triple barrier spans

### Additional Feature Engineering
- [ ] Compute multi-horizon raw returns (1-day, 2-day, 3-day, 5-day, 10-day log returns)
- [ ] Implement Garman-Klass and Parkinson volatility estimators to quantify daily intraday range
- [ ] Implement volatility regime indicator categorizing market state into low, medium, and high volatility bins
- [ ] Implement calendar features (day of week, day of month, month of year, quarter-end flags)

### XGBoost & Hyperparameter Optimization
- [ ] Implement XGBoost classification training pipeline in `src/darefx/models/xgboost_trainer.py`
- [ ] Build Optuna hyperparameter optimization runner in `src/darefx/models/tuner.py`
- [ ] Define hyperparameter search spaces for LightGBM and XGBoost (depth, learning rate, subsample, regularization)
- [ ] Run 100+ Optuna optimization trials per model maximizing out-of-sample Sharpe ratio with early stopping
- [ ] Implement probability ensemble model combining weighted LightGBM and XGBoost predictions

### Realistic Cost Modeling & Performance Metrics
- [ ] Implement variable spread model reflecting London/New York session liquidity vs Asian session illiquidity
- [ ] Implement execution slippage simulation fixed at 1.0 pip per market execution and broker commissions
- [ ] Implement metrics suite in `src/darefx/backtest/metrics.py`: Sharpe, Sortino, and Calmar ratios
- [ ] Implement trade metrics: maximum drawdown, average drawdown depth, win rate, profit factor, expectancy, and holding duration
- [ ] Write unit tests verifying metric formulas against manual calculations

### Model Registry & Decision Gate
- [ ] Implement model registry saving serialized model binaries, feature schemas, and performance metrics in `src/darefx/models/registry.py`
- [ ] Create Jupyter notebook `notebooks/03_model_experiments.ipynb` comparing LightGBM, XGBoost, and ensemble results
- [ ] Execute Decision Gate review: verify whether candidate model achieves out-of-sample Sharpe > 1.0 (minimum threshold > 0.5)

---

## Phase 4: Paper Trading Infrastructure (Month 4-5)

### MetaTrader 5 Bridge
- [ ] Install and configure MetaTrader 5 terminal on Linux Mint via Wine or configure Windows execution host
- [ ] Implement MT5 connection initialization, account authentication, and ping heartbeat in `src/darefx/trading/mt5_bridge.py`
- [ ] Implement live tick data streamer and historical daily bar query functions
- [ ] Implement market order execution module sending BUY and SELL requests with stop-loss and take-profit parameters
- [ ] Implement position query and trade history reconciliation functions

### Risk Management & Sizing Engine
- [ ] Implement fixed fractional position sizing module (1.0% to 2.0% equity at risk per trade) in `src/darefx/risk/position_sizer.py`
- [ ] Implement half-Kelly criterion calculator bounded by the fixed fractional risk ceiling
- [ ] Implement circuit breaker state machine in `src/darefx/risk/circuit_breaker.py` (5.0% daily halt, 15.0% total drawdown halt)
- [ ] Implement position constraint enforcer restricting concurrent trades to 1 position on EUR/USD with zero martingale scaling
- [ ] Write unit tests covering position sizing calculations and circuit breaker state transitions

### Telegram Notification Service
- [ ] Register new Telegram bot via BotFather and store API token and target chat ID in `.env`
- [ ] Implement asynchronous Telegram messaging client in `src/darefx/notifications/telegram_bot.py`
- [ ] Implement trade execution alert formatter (order type, entry price, lot size, stop loss, take profit)
- [ ] Implement daily summary alert formatter (account balance, closed P&L, open positions, daily return percentage)
- [ ] Implement circuit breaker alert dispatch notifying of trading halts or system exceptions

### Execution Loop & System Deployment
- [ ] Implement main execution loop orchestrating bar ingestion, feature computation, prediction, and order placement in `src/darefx/trading/bot.py`
- [ ] Configure scheduled execution trigger at 17:00 New York EST daily close
- [ ] Implement bar completion validator confirming daily candle is finalized before model inference
- [ ] Write systemd unit configuration file `darefx.service` with automatic restart on failure and structured JSON logging
- [ ] Execute 7-day unattended demo run on Valetax verifying zero crashes, correct daily scheduling, and prompt Telegram alerts

---

## Phase 5: Evaluation + Go/No-Go Decision (Month 6)

### Paper Trading Reconciliation & Slippage
- [ ] Export 3+ months of execution logs, fill prices, slippage records, and balance history from MT5
- [ ] Reconcile recorded paper trades against theoretical signals generated by the model pipeline
- [ ] Calculate realized slippage distribution and compare against the 1.0 pip assumption used in backtesting
- [ ] Evaluate spread distributions at 17:00 EST market roll to measure liquidity friction

### Statistical Verification & Regime Analysis
- [ ] Calculate realized Sharpe, Sortino, Calmar, win rate, and profit factor on paper trading returns
- [ ] Compute Deflated Sharpe Ratio (DSR) to test statistical significance against backtest multiple testing
- [ ] Compare paper trading performance across trending, consolidating, and high-volatility regimes
- [ ] Compare realized trade holding durations against theoretical triple barrier exit distributions

### Evaluation Report & Decision Gate
- [ ] Author formal evaluation report in `docs/EVALUATION-REPORT.md` compiling all comparative performance statistics
- [ ] Evaluate GO criteria: Paper trading Sharpe > 0.8, max drawdown < 15%, execution slippage <= 1.5 pips
- [ ] Evaluate ITERATE condition: Sharpe between 0.3 and 0.8, identifiable feature or execution discrepancies
- [ ] Evaluate STOP condition: Sharpe <= 0.3, max drawdown >= 20%, failure to demonstrate statistical edge
- [ ] Prepare production VPS deployment checklist if GO criteria are satisfied
