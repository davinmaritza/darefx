"""DareFX Command Line Interface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from darefx import __version__
from darefx.data.downloader import DukascopyDownloader, YahooFinanceDownloader
from darefx.data.preprocessor import resample_ticks_to_daily
from darefx.data.storage import ParquetStorage

app = typer.Typer(help="DareFX — AI-powered EUR/USD Forex Auto-Trading System")
console = Console()


@app.command()
def version() -> None:
    """Print the DareFX version."""
    console.print(f"[bold cyan]DareFX[/bold cyan] version [green]{__version__}[/green]")


@app.command()
def fetch(
    source: str = typer.Option("yahoo", help="Data source: 'yahoo' (recommended) or 'dukascopy'"),
    symbol: str = typer.Option("EURUSD", help="Currency pair (e.g. EURUSD)"),
    range_str: str = typer.Option("25y", help="Historical range for yahoo (e.g. '5y', '10y', '25y')"),
    output_dir: str = typer.Option("data/processed", help="Output directory for Parquet storage"),
) -> None:
    """Download historical forex data and store as partition-ready Parquet files."""
    console.print(f"[bold cyan]Initiating DareFX Data Ingestion for {symbol} (Source: {source.upper()})...[/bold cyan]")

    if source.lower() == "yahoo":
        yahoo_sym = f"{symbol}=X" if not symbol.endswith("=X") else symbol
        downloader = YahooFinanceDownloader(symbol=yahoo_sym)
        console.print(f"Downloading up to {range_str} of daily OHLCV bars directly from Yahoo Finance...")
        df_bars = downloader.fetch_daily_bars(range_str=range_str)

        if df_bars.empty:
            console.print("[red]Failed to retrieve data from Yahoo Finance.[/red]")
            return

        storage = ParquetStorage(base_dir=output_dir)
        saved_files = storage.save_daily_bars(df_bars, symbol=symbol, partition_by_year=True)

        first_date = df_bars['timestamp'].iloc[0].strftime('%Y-%m-%d')
        last_date = df_bars['timestamp'].iloc[-1].strftime('%Y-%m-%d')
        console.print(f"[bold green]Successfully ingested {len(df_bars):,} daily bars from {first_date} to {last_date}![/bold green]")
        console.print(f"Stored across [bold green]{len(saved_files)}[/bold green] annual Parquet partitions in `{output_dir}/`.")

        # Show recent 5 bars preview
        table = Table(title=f"Sample Recent Bars: {symbol}")
        table.add_column("Date (UTC)", style="cyan")
        table.add_column("Open", style="white")
        table.add_column("High", style="green")
        table.add_column("Low", style="red")
        table.add_column("Close", style="white")
        table.add_column("Volume", style="magenta")

        for _, row in df_bars.tail(5).iterrows():
            table.add_row(
                str(row["timestamp"].strftime("%Y-%m-%d")),
                f"{row['open']:.5f}",
                f"{row['high']:.5f}",
                f"{row['low']:.5f}",
                f"{row['close']:.5f}",
                f"{row['volume']:,.0f}",
            )
        console.print(table)

    elif source.lower() == "dukascopy":
        console.print("[yellow]Note: Dukascopy servers may be blocked by some Indonesian ISPs without a VPN.[/yellow]")
        start_dt = datetime(2024, 1, 8, tzinfo=UTC)
        end_dt = datetime(2024, 1, 9, tzinfo=UTC)
        downloader = DukascopyDownloader(symbol=symbol)
        df_ticks = downloader.fetch_range(start_dt, end_dt)

        if df_ticks.empty:
            console.print("[red]No ticks downloaded (possibly blocked by ISP). Try using '--source yahoo'.[/red]")
            return

        df_bars = resample_ticks_to_daily(df_ticks)
        storage = ParquetStorage(base_dir=output_dir)
        saved_files = storage.save_daily_bars(df_bars, symbol=symbol, partition_by_year=True)
        console.print(f"[green]Successfully saved {len(df_bars)} daily bars from Dukascopy.[/green]")
    else:
        console.print(f"[red]Unknown source '{source}'. Available: 'yahoo', 'dukascopy'[/red]")


@app.command()
def info(
    symbol: str = typer.Option("EURUSD", help="Currency pair"),
    data_dir: str = typer.Option("data/processed", help="Data directory"),
) -> None:
    """Display summary and statistics of stored historical datasets."""
    storage = ParquetStorage(base_dir=data_dir)
    df = storage.load_daily_bars(symbol=symbol)

    if df.empty:
        console.print(f"[yellow]No data found for {symbol} in {data_dir}. Run 'darefx fetch' first.[/yellow]")
        return

    first_date = df['timestamp'].iloc[0].strftime('%Y-%m-%d')
    last_date = df['timestamp'].iloc[-1].strftime('%Y-%m-%d')

    console.print(f"[bold cyan]Dataset Summary: {symbol}[/bold cyan]")
    console.print(f"Total Daily Bars: [bold green]{len(df):,}[/bold green]")
    console.print(f"Historical Span: [green]{first_date}[/green] to [green]{last_date}[/green]")
    console.print(f"Price Range: [red]{df['low'].min():.5f}[/red] to [green]{df['high'].max():.5f}[/green]")
    console.print(f"Mean Close: [white]{df['close'].mean():.5f}[/white]")


@app.command()
def features(
    symbol: str = typer.Option("EURUSD", help="Currency pair"),
    data_dir: str = typer.Option("data/processed", help="Data directory"),
    pt: float = typer.Option(1.5, help="Profit target multiplier (x ATR)"),
    sl: float = typer.Option(1.5, help="Stop loss multiplier (x ATR)"),
    holding: int = typer.Option(5, help="Max holding window in daily bars"),
) -> None:
    """Extract technical indicators and apply Triple Barrier labeling."""
    from darefx.features.labels import TripleBarrierConfig
    from darefx.features.pipeline import build_feature_dataset

    console.print(f"[bold cyan]Building ML Feature Matrix for {symbol}...[/bold cyan]")
    config = TripleBarrierConfig(pt_multiplier=pt, sl_multiplier=sl, max_holding_bars=holding)

    try:
        df_dataset, feature_names = build_feature_dataset(
            symbol=symbol,
            data_dir=data_dir,
            config=config,
            save_output=True,
        )
    except Exception as err:
        console.print(f"[red]Error building features: {err}[/red]")
        return

    console.print("[bold green]Feature matrix generated successfully![/bold green]")
    console.print(f"Total Samples: [cyan]{len(df_dataset):,}[/cyan]")
    console.print(f"Total Engineered Features: [cyan]{len(feature_names)}[/cyan]")

    target_counts = df_dataset["barrier_target"].value_counts()
    table = Table(title="Triple Barrier Target Distribution")
    table.add_column("Target Class", style="cyan")
    table.add_column("Label Name", style="white")
    table.add_column("Count", style="green")
    table.add_column("Percentage", style="magenta")

    names = {1: "Profit Target Touched (+1)", -1: "Stop Loss Touched (-1)", 0: "Vertical Barrier Expired (0)"}
    for label, count in target_counts.items():
        pct = (count / len(df_dataset)) * 100.0
        table.add_row(str(label), names.get(label, "Unknown"), f"{count:,}", f"{pct:.2f}%")

    console.print(table)
    console.print(f"Saved dataset: [bold green]{data_dir}/{symbol.lower()}_features.parquet[/bold green]")


@app.command()
def train(
    symbol: str = typer.Option("EURUSD", help="Currency pair"),
    data_dir: str = typer.Option("data/processed", help="Data directory containing features parquet"),
    model_dir: str = typer.Option("data/models", help="Directory to save trained model artifact"),
    train_months: int = typer.Option(36, help="Walk-forward training window in months"),
    test_months: int = typer.Option(6, help="Walk-forward testing window in months"),
    step_months: int = typer.Option(3, help="Walk-forward step in months"),
    purge_days: int = typer.Option(10, help="Purge gap in calendar days"),
) -> None:
    """Execute Walk-Forward evaluation and train production LightGBM model."""
    import pandas as pd

    from darefx.features.pipeline import EXCLUDE_FROM_FEATURES
    from darefx.models.trainer import LightGBMConfig, LightGBMTrainer
    from darefx.models.validator import WalkForwardConfig

    dataset_path = Path(data_dir) / f"{symbol.lower()}_features.parquet"
    if not dataset_path.exists():
        console.print(f"[red]Feature dataset not found at {dataset_path}. Run 'darefx features' first.[/red]")
        return

    console.print(f"[bold cyan]Loading features for {symbol} from {dataset_path}...[/bold cyan]")
    df_dataset = pd.read_parquet(dataset_path)

    feature_cols = [c for c in df_dataset.columns if c not in EXCLUDE_FROM_FEATURES]
    console.print(f"Dataset: [green]{len(df_dataset):,}[/green] samples x [green]{len(feature_cols)}[/green] features.")

    wf_config = WalkForwardConfig(
        train_months=train_months,
        test_months=test_months,
        step_months=step_months,
        purge_days=purge_days,
    )

    console.print(f"[bold yellow]Executing Purged Walk-Forward Cross-Validation ({train_months}m Train / {test_months}m Test / {step_months}m Step)...[/bold yellow]")

    trainer = LightGBMTrainer(config=LightGBMConfig())
    result = trainer.evaluate_walk_forward(
        df_dataset=df_dataset,
        feature_cols=feature_cols,
        target_col="barrier_target",
        time_col="timestamp",
        wf_config=wf_config,
    )

    console.print(f"[bold green]Walk-Forward Completed across {result.num_folds} folds![/bold green]")
    console.print(f"Total Out-Of-Sample Predictions: [cyan]{result.total_samples:,}[/cyan]")
    console.print(f"Overall OOS Accuracy: [bold white]{result.overall_accuracy * 100:.2f}%[/bold white]")
    console.print(f"Overall OOS Multi-LogLoss: [bold white]{result.overall_log_loss:.4f}[/bold white]")

    # Classification breakdown
    table = Table(title="Out-Of-Sample Classification Report")
    table.add_column("Class", style="cyan")
    table.add_column("Precision", style="white")
    table.add_column("Recall", style="green")
    table.add_column("F1-Score", style="magenta")
    table.add_column("Support", style="yellow")

    for class_name in ["Sell (-1)", "Neutral (0)", "Buy (+1)"]:
        metrics = result.class_report.get(class_name, {})
        table.add_row(
            class_name,
            f"{metrics.get('precision', 0.0) * 100:.2f}%",
            f"{metrics.get('recall', 0.0) * 100:.2f}%",
            f"{metrics.get('f1-score', 0.0):.4f}",
            f"{metrics.get('support', 0):,}",
        )
    console.print(table)

    # Top 10 feature importance
    imp_table = Table(title="Top 10 Feature Importance (by Gain)")
    imp_table.add_column("Rank", style="cyan")
    imp_table.add_column("Feature", style="white")
    imp_table.add_column("Importance Gain", style="green")

    for rank, (_, row) in enumerate(result.feature_importance.head(10).iterrows(), 1):
        imp_table.add_row(str(rank), str(row["feature"]), f"{row['importance_gain']:.2f}")
    console.print(imp_table)

    # Save OOS predictions
    oos_out = Path(data_dir) / f"{symbol.lower()}_oos_predictions.parquet"
    result.out_of_sample_df.to_parquet(oos_out, compression="snappy", index=False)
    console.print(f"Saved OOS predictions: [bold green]{oos_out}[/bold green]")

    # Train final full model for production
    console.print("Training final production model on full dataset...")
    final_trainer = LightGBMTrainer(config=LightGBMConfig())
    final_trainer.fit(df_dataset[feature_cols], df_dataset["barrier_target"])
    model_path = Path(model_dir) / f"lightgbm_{symbol.lower()}.joblib"
    final_trainer.save(model_path)
    console.print(f"Saved production model artifact: [bold green]{model_path}[/bold green]")


@app.command()
def backtest(
    symbol: str = typer.Option("EURUSD", help="Currency pair"),
    data_dir: str = typer.Option("data/processed", help="Data directory containing OOS predictions"),
    capital: float = typer.Option(10_000.0, help="Initial account equity in USD"),
    risk: float = typer.Option(1.0, help="Percent risk per trade (e.g. 1.0%)"),
    spread: float = typer.Option(1.5, help="Round-trip spread in pips"),
    slippage: float = typer.Option(1.0, help="Slippage in pips"),
    threshold: float = typer.Option(0.40, help="Minimum probability threshold to enter trade"),
    adx_min: float = typer.Option(0.0, help="Minimum ADX trend strength filter"),
    sl: float = typer.Option(1.5, help="Stop loss multiplier (x ATR)"),
    pt: float = typer.Option(1.5, help="Profit target multiplier (x ATR)"),
) -> None:
    """Run realistic out-of-sample backtest with transaction costs and fixed fractional risk."""
    import pandas as pd

    from darefx.backtest.engine import BacktestConfig, BacktestEngine

    oos_path = Path(data_dir) / f"{symbol.lower()}_oos_predictions.parquet"
    if not oos_path.exists():
        console.print(f"[red]OOS predictions file not found at {oos_path}. Run 'darefx train' first.[/red]")
        return

    console.print(f"[bold cyan]Running Out-Of-Sample Backtest on {symbol}...[/bold cyan]")
    df_oos = pd.read_parquet(oos_path)

    if adx_min > 0.0 and "adx_14" in df_oos.columns:
        weak_mask = df_oos["adx_14"] < adx_min
        df_oos.loc[weak_mask, "prob_buy"] = 0.0
        df_oos.loc[weak_mask, "prob_sell"] = 0.0

    config = BacktestConfig(
        initial_capital=capital,
        risk_per_trade_pct=risk,
        spread_pips=spread,
        slippage_pips=slippage,
        confidence_threshold=threshold,
        sl_multiplier=sl,
        pt_multiplier=pt,
    )

    engine = BacktestEngine(config=config)
    result = engine.run(df_oos)
    m = result.metrics

    table = Table(title=f"DareFX Out-Of-Sample Performance Summary ({symbol})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold white")
    table.add_column("Benchmark / Target", style="yellow")

    table.add_row("Initial Capital", f"${m.initial_balance:,.2f}", "$10,000.00")
    table.add_row("Final Balance", f"${m.final_balance:,.2f}", "> Initial Capital")
    table.add_row("Total Return", f"{m.total_return_pct:+.2f}%", "> 0.00%")
    table.add_row("CAGR (Annualized Return)", f"{m.cagr_pct:+.2f}%", "> 10.00% (S&P500)")
    table.add_row("Annualized Volatility", f"{m.annualized_volatility_pct:.2f}%", "< 15.00%")
    table.add_row("Sharpe Ratio", f"{m.sharpe_ratio:.2f}", "> 1.00 (Institutional Target)")
    table.add_row("Sortino Ratio", f"{m.sortino_ratio:.2f}", "> 1.50")
    table.add_row("Calmar Ratio", f"{m.calmar_ratio:.2f}", "> 0.60")
    table.add_row("Max Drawdown", f"{m.max_drawdown_pct:.2f}%", "< 20.00% (Hard Limit)")
    table.add_row("Max Drawdown Duration", f"{m.max_drawdown_duration_days} days", "-")
    table.add_row("Win Rate", f"{m.win_rate_pct:.2f}%", "> 50.00%")
    table.add_row("Profit Factor", f"{m.profit_factor:.2f}", "> 1.30")
    table.add_row("Total Trades Executed", f"{m.total_trades:,}", "N >= 100 for significance")
    table.add_row("Winning / Losing Trades", f"{m.winning_trades} / {m.losing_trades}", "-")
    table.add_row("Avg Win / Avg Loss", f"${m.avg_win_usd:.2f} / ${m.avg_loss_usd:.2f}", "Win/Loss > 1.0")
    table.add_row("Trade Expectancy", f"${m.expectancy_usd:+.2f} per trade", "> $0.00")

    console.print(table)

    # Save trades
    trades_path = Path(data_dir) / f"{symbol.lower()}_backtest_trades.csv"
    result.trade_log.to_csv(trades_path, index=False)
    console.print(f"Saved trade log to [bold green]{trades_path}[/bold green]")


@app.command()
def tune(
    symbol: str = typer.Option("EURUSD", help="Currency pair"),
    data_dir: str = typer.Option("data/processed", help="Data directory containing OOS predictions"),
    trials: int = typer.Option(35, help="Number of Bayesian optimization trials"),
    metric: str = typer.Option("sharpe", help="Optimization target: 'sharpe' or 'profit_factor'"),
) -> None:
    """Run Optuna Bayesian hyperparameter search to discover profitable execution parameters."""
    import pandas as pd

    from darefx.backtest.engine import BacktestConfig, BacktestEngine
    from darefx.models.tuner import HyperparameterTuner

    oos_path = Path(data_dir) / f"{symbol.lower()}_oos_predictions.parquet"
    if not oos_path.exists():
        console.print(f"[red]OOS predictions file not found at {oos_path}. Run 'darefx train' first.[/red]")
        return

    console.print(f"[bold cyan]Initiating Optuna Optimization ({trials} trials, target: {metric.upper()})...[/bold cyan]")
    df_oos = pd.read_parquet(oos_path)

    tuner = HyperparameterTuner(df_features=df_oos, feature_cols=[], n_trials=trials, target_metric=metric)
    opt_result = tuner.optimize_execution_policy(df_oos=df_oos)

    best_score = opt_result["best_score"]
    best_params = opt_result["best_params"]

    console.print(f"[bold green]Optimization Finished! Best {metric.upper()}: {best_score:.2f}[/bold green]")

    param_table = Table(title="Optimal Policy Parameters (Optuna)")
    param_table.add_column("Parameter", style="cyan")
    param_table.add_column("Optimal Value", style="bold green")

    for k, v in best_params.items():
        if isinstance(v, float):
            param_table.add_row(k, f"{v:.4f}")
        else:
            param_table.add_row(k, str(v))
    console.print(param_table)

    # Re-run backtest using the discovered optimal policy
    console.print("[bold yellow]Validating Out-Of-Sample Performance with Optimal Policy...[/bold yellow]")
    df_eval = df_oos.copy()
    adx_min = best_params.get("adx_min", 0.0)
    if "adx_14" in df_eval.columns and adx_min > 0:
        weak_mask = df_eval["adx_14"] < adx_min
        df_eval.loc[weak_mask, "prob_buy"] = 0.0
        df_eval.loc[weak_mask, "prob_sell"] = 0.0

    best_config = BacktestConfig(
        initial_capital=10_000.0,
        risk_per_trade_pct=1.0,
        spread_pips=1.5,
        slippage_pips=1.0,
        confidence_threshold=best_params["threshold"],
        sl_multiplier=best_params["sl_multiplier"],
        pt_multiplier=best_params["pt_multiplier"],
    )

    engine = BacktestEngine(config=best_config)
    eval_result = engine.run(df_eval)
    m = eval_result.metrics

    table = Table(title=f"Optimized Out-Of-Sample Performance ({symbol})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold white")
    table.add_column("Benchmark / Target", style="yellow")

    table.add_row("Initial Capital", f"${m.initial_balance:,.2f}", "$10,000.00")
    table.add_row("Final Balance", f"${m.final_balance:,.2f}", "> Initial Capital")
    table.add_row("Total Return", f"{m.total_return_pct:+.2f}%", "> 0.00%")
    table.add_row("CAGR (Annualized Return)", f"{m.cagr_pct:+.2f}%", "> 10.00% (S&P500)")
    table.add_row("Annualized Volatility", f"{m.annualized_volatility_pct:.2f}%", "< 15.00%")
    table.add_row("Sharpe Ratio", f"{m.sharpe_ratio:.2f}", "> 1.00 (Target)")
    table.add_row("Sortino Ratio", f"{m.sortino_ratio:.2f}", "> 1.50")
    table.add_row("Calmar Ratio", f"{m.calmar_ratio:.2f}", "> 0.60")
    table.add_row("Max Drawdown", f"{m.max_drawdown_pct:.2f}%", "< 20.00% (Hard Limit)")
    table.add_row("Win Rate", f"{m.win_rate_pct:.2f}%", "> 50.00%")
    table.add_row("Profit Factor", f"{m.profit_factor:.2f}", "> 1.30")
    table.add_row("Total Trades Executed", f"{m.total_trades:,}", "Statistical Significance")
    table.add_row("Trade Expectancy", f"${m.expectancy_usd:+.2f} per trade", "> $0.00")

    console.print(table)

    trades_path = Path(data_dir) / f"{symbol.lower()}_backtest_trades.csv"
    eval_result.trade_log.to_csv(trades_path, index=False)
    console.print(f"Saved optimized trade log to [bold green]{trades_path}[/bold green]")


@app.command(name="tune-model")
def tune_model(
    symbol: str = typer.Option("EURUSD", help="Currency pair"),
    data_dir: str = typer.Option("data/processed", help="Data directory containing features parquet"),
    model_dir: str = typer.Option("data/models", help="Directory to save tuned model artifact"),
    trials: int = typer.Option(20, help="Number of Bayesian optimization trials"),
) -> None:
    """Run Optuna Bayesian tuning on LightGBM tree structure and regularization."""
    import pandas as pd

    from darefx.features.pipeline import EXCLUDE_FROM_FEATURES
    from darefx.models.trainer import LightGBMConfig, LightGBMTrainer
    from darefx.models.tuner import HyperparameterTuner

    dataset_path = Path(data_dir) / f"{symbol.lower()}_features.parquet"
    if not dataset_path.exists():
        console.print(f"[red]Feature dataset not found at {dataset_path}. Run 'darefx features' first.[/red]")
        return

    console.print(f"[bold cyan]Initiating LightGBM Architecture & Regularization Tuning ({trials} trials)...[/bold cyan]")
    df_dataset = pd.read_parquet(dataset_path)
    feature_cols = [c for c in df_dataset.columns if c not in EXCLUDE_FROM_FEATURES]

    tuner = HyperparameterTuner(df_features=df_dataset, feature_cols=feature_cols, n_trials=trials)
    tune_res = tuner.optimize_model_hyperparameters(
        df_dataset=df_dataset,
        feature_cols=feature_cols,
        step_months=6,
    )

    best_params = tune_res["best_params"]
    console.print(f"[bold green]Model Tuning Complete! Lowest Validation Log-Loss: {tune_res['best_loss']:.4f}[/bold green]")

    param_table = Table(title="Tuned LightGBM Hyperparameters")
    param_table.add_column("Hyperparameter", style="cyan")
    param_table.add_column("Optimal Value", style="bold green")

    for k, v in best_params.items():
        param_table.add_row(k, f"{v:.5f}" if isinstance(v, float) else str(v))
    console.print(param_table)

    # Train and save the newly tuned production model
    console.print("Training new production model using optimal hyperparameters...")
    best_config = LightGBMConfig(
        n_estimators=250,
        learning_rate=best_params["learning_rate"],
        max_depth=best_params["max_depth"],
        num_leaves=best_params["num_leaves"],
        min_child_samples=best_params["min_child_samples"],
        subsample=best_params["subsample"],
        colsample_bytree=best_params["colsample_bytree"],
        reg_alpha=best_params["reg_alpha"],
        reg_lambda=best_params["reg_lambda"],
    )
    tuned_trainer = LightGBMTrainer(config=best_config)
    tuned_trainer.fit(df_dataset[feature_cols], df_dataset["barrier_target"])
    model_path = Path(model_dir) / f"lightgbm_{symbol.lower()}.joblib"
    tuned_trainer.save(model_path)
    console.print(f"Saved tuned production model artifact: [bold green]{model_path}[/bold green]")


@app.command(name="run-cycle")

def run_cycle(
    symbol: str = typer.Option("EURUSD", help="Currency pair"),
    equity: float = typer.Option(10_000.0, help="Current account equity in USD"),
    threshold: float = typer.Option(0.46, help="Confidence threshold"),
    adx_min: float = typer.Option(32.0, help="Minimum ADX trend strength"),
    risk_pct: float = typer.Option(1.0, help="Risk per trade in percent"),
    execute: bool = typer.Option(False, "--execute", help="Execute order via MT5 Bridge (paper/live)"),
) -> None:
    """Run a single daily trading cycle: ingest, feature extraction, ML inference, and alert."""
    from darefx.trading.bot import BotConfig, TradingBot

    mode_label = "[bold red]LIVE / PAPER EXECUTION[/bold red]" if execute else "[bold cyan]SIMULATION / ALERT ONLY[/bold cyan]"
    console.print(f"[bold cyan]Initiating DareFX Daily Trading Cycle for {symbol} ({mode_label})...[/bold cyan]")

    config = BotConfig(
        symbol=symbol,
        confidence_threshold=threshold,
        adx_min=adx_min,
        risk_pct=risk_pct,
        execute_orders=execute,
    )
    bot = TradingBot(config=config)
    result = bot.run_daily_cycle(current_equity=equity)

    status = result.get("status")
    if status == "signal_dispatched":
        action = result["action"]
        color = "green" if action == "BUY" else "red"
        console.print(f"[{color}]SIGNAL GENERATED: {action} {result['lots']:.2f} lots @ {result['entry_price']:.5f}[/{color}]")
        console.print(f"Stop Loss: [red]{result['stop_loss']:.5f}[/red] | Take Profit: [green]{result['take_profit']:.5f}[/green]")
        console.print(f"Confidence: [cyan]{result['confidence'] * 100:.1f}%[/cyan] | ADX: [yellow]{result['adx']:.1f}[/yellow]")
        if execute:
            console.print(f"Order Ticket: [bold white]#{result.get('ticket')}[/bold white] (Status: {result.get('execution_status')})")
    elif status == "filtered_by_regime":
        console.print(f"[yellow]Trade filtered by regime: {result.get('reason')}[/yellow]")
    elif status == "no_signal":
        console.print(f"[white]No trade signal generated: {result.get('reason')}[/white]")
    elif status == "blocked_by_circuit_breaker":
        console.print(f"[bold red]CIRCUIT BREAKER BLOCKED TRADE: {result.get('reason')}[/bold red]")
    else:
        console.print(f"[red]Execution status: {result}[/red]")


@app.command(name="run-multi")
def run_multi(
    equity: float = typer.Option(10_000.0, help="Total account equity in USD"),
    execute: bool = typer.Option(
        False, "--execute", help="Execute orders via live/paper broker connections"
    ),
    once: bool = typer.Option(
        True, "--once/--daemon", help="Run single cycle immediately or run continuous daemon"
    ),
    forex_symbols: str = typer.Option(
        "EURUSD,GBPUSD,USDJPY", help="Forex symbols (comma-separated)"
    ),
    crypto_symbols: str = typer.Option(
        "BTC/USDT,ETH/USDT,SOL/USDT", help="Crypto pairs (comma-separated)"
    ),
    stock_symbols: str = typer.Option(
        "NVDA,AAPL,MSFT,AMZN,TSLA", help="Stock symbols (comma-separated)"
    ),
    max_positions: int = typer.Option(
        5, help="Maximum concurrent positions across all asset classes"
    ),
) -> None:
    """Run unified cross-asset scanning and risk-governed execution across Forex, Crypto, Stocks."""
    import time

    from darefx.risk.portfolio_governor import PortfolioGovernor, PortfolioGovernorConfig
    from darefx.trading.multi_scheduler import MultiScheduler, MultiSchedulerConfig

    fx_list = [s.strip().upper() for s in forex_symbols.split(",") if s.strip()]
    crypto_list = [s.strip().upper() for s in crypto_symbols.split(",") if s.strip()]
    stock_list = [s.strip().upper() for s in stock_symbols.split(",") if s.strip()]

    mode_label = (
        "[bold red]LIVE / PAPER EXECUTION[/bold red]"
        if execute
        else "[bold cyan]SIMULATION / ALERT ONLY[/bold cyan]"
    )
    banner_msg = (
        f"[bold cyan]Initiating DareFX Unified Multi-Asset Engine "
        f"({mode_label})...[/bold cyan]"
    )
    console.print(banner_msg)



    config = MultiSchedulerConfig(
        forex_symbols=fx_list,
        crypto_symbols=crypto_list,
        stock_symbols=stock_list,
        account_equity=equity,
        execute_orders=execute,
    )
    governor = PortfolioGovernor(
        config=PortfolioGovernorConfig(
            max_total_positions=max_positions,
            max_positions_per_asset={"forex": 2, "crypto": 2, "stocks": 2},
        )
    )
    scheduler = MultiScheduler(config=config, governor=governor)

    if once:
        scan_msg = (
            f"Scanning {len(fx_list)} Forex pairs, {len(crypto_list)} Crypto pairs, "
            f"and {len(stock_list)} Stocks..."
        )
        console.print(scan_msg)
        results = scheduler.run_all_cycles()

        table = Table(title="DareFX Multi-Asset Trade Dispatch Summary")
        table.add_column("Asset Class", style="cyan")
        table.add_column("Symbol", style="bold white")
        table.add_column("Action", style="white")
        table.add_column("Entry", style="green")
        table.add_column("Stop Loss", style="red")
        table.add_column("Take Profit", style="green")
        table.add_column("Confidence", style="yellow")
        table.add_column("Status / Ticket", style="bold magenta")

        total_orders = 0
        for asset_key, items in results.items():
            for it in items:
                total_orders += 1
                action = it.get("action", "BUY")
                act_color = "green" if action == "BUY" else "red"
                status_txt = f"{it.get('status')} (#{it.get('ticket', 0)})"
                table.add_row(
                    asset_key.upper(),
                    it.get("symbol", "-"),
                    f"[{act_color}]{action}[/{act_color}]",
                    f"{it.get('entry_price', 0.0):.4f}",
                    f"{it.get('stop_loss', 0.0):.4f}",
                    f"{it.get('take_profit', 0.0):.4f}",
                    f"{it.get('confidence', 0.0) * 100:.1f}%",
                    status_txt,
                )

        if total_orders > 0:
            console.print(table)
        else:
            no_orders_msg = (
                "[yellow]All scanned markets evaluated. "
                "No new setups met threshold or capacity bounds.[/yellow]"
            )
            console.print(no_orders_msg)
    else:
        console.print("[bold green]Starting daemon scheduler. Press Ctrl+C to terminate.[/bold green]")
        scheduler.start()
        try:
            while scheduler.is_running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            console.print("[yellow]Stopping MultiScheduler daemon...[/yellow]")
            scheduler.stop()
            console.print("[green]MultiScheduler daemon safely stopped.[/green]")


@app.command(name="backtest-multi")
def backtest_multi(
    start: str = typer.Option("2023-01-01", help="Backtest start date (YYYY-MM-DD)"),
    end: str = typer.Option("2026-11-01", help="Backtest end date (YYYY-MM-DD)"),
    equity: float = typer.Option(10_000.0, help="Initial account equity in USD"),
    risk_pct: float = typer.Option(1.0, help="Risk percent per trade"),
    export_csv: str = typer.Option(None, help="Optional path to export daily equity curve CSV"),
) -> None:
    """Run cross-portfolio multi-asset backtest across Forex, Crypto, and Stocks."""
    from darefx.analysis.multi_backtester import MultiAssetBacktestConfig, MultiAssetBacktester

    console.print(
        f"[bold cyan]Running DareFX Multi-Asset Cross-Portfolio Backtest "
        f"({start} to {end})...[/bold cyan]"
    )

    config = MultiAssetBacktestConfig(
        start_date=start,
        end_date=end,
        initial_equity=equity,
        risk_per_trade_pct=risk_pct,
    )
    backtester = MultiAssetBacktester(config=config)
    res = backtester.run()

    # 1. Summary Metrics Table
    summary_table = Table(title="DareFX Multi-Asset Portfolio Performance")
    summary_table.add_column("Metric", style="white")
    summary_table.add_column("Value", style="bold green")
    summary_table.add_column("Assessment", style="cyan")

    ret_color = "green" if res.total_return_pct >= 0 else "red"
    summary_table.add_row(
        "Capital Trajectory",
        f"${res.initial_equity:,.2f} -> ${res.final_equity:,.2f}",
        f"[{ret_color}]{res.total_return_pct:+.2f}% total[/{ret_color}]",
    )
    summary_table.add_row(
        "Annualized Return",
        f"{res.annualized_return_pct:+.2f}%",
        "Compound annual growth",
    )
    summary_table.add_row(
        "Maximum Drawdown",
        f"{res.max_drawdown_pct:.2f}% (${res.max_drawdown_usd:,.2f})",
        "Peak-to-valley loss",
    )
    summary_table.add_row(
        "Portfolio Sharpe Ratio",
        f"{res.portfolio_sharpe:.2f}",
        "High alpha" if res.portfolio_sharpe > 1.5 else "Moderate",
    )
    summary_table.add_row(
        "Portfolio Sortino Ratio",
        f"{res.portfolio_sortino:.2f}",
        "Downside-adjusted edge",
    )
    summary_table.add_row(
        "Win Rate & Trades",
        f"{res.overall_win_rate:.1f}% ({res.winning_trades}W / {res.losing_trades}L)",
        f"{res.total_trades} total closed setups",
    )
    summary_table.add_row(
        "Overall Profit Factor",
        f"{res.overall_profit_factor:.2f}",
        "Gross profit / gross loss",
    )
    console.print(summary_table)

    # 2. Asset Breakdown Table
    asset_table = Table(title="Performance by Asset Class")
    asset_table.add_column("Asset Class", style="bold white")
    asset_table.add_column("Trades", style="cyan")
    asset_table.add_column("Win Rate", style="yellow")
    asset_table.add_column("Net Profit ($)", style="green")
    asset_table.add_column("Profit Factor", style="magenta")

    for k, ap in res.asset_breakdown.items():
        np_color = "green" if ap.net_profit >= 0 else "red"
        asset_table.add_row(
            ap.asset_class,
            str(ap.total_trades),
            f"{ap.win_rate:.1f}%",
            f"[{np_color}]${ap.net_profit:+,.2f}[/{np_color}]",
            f"{ap.profit_factor:.2f}",
        )
    console.print(asset_table)

    # 3. Cross-Asset Correlation Table
    corr_table = Table(title="Cross-Asset Daily Return Correlation (Diversification Matrix)")
    corr_table.add_column("Asset", style="bold white")
    corr_table.add_column("Forex", style="cyan")
    corr_table.add_column("Crypto", style="yellow")
    corr_table.add_column("Stocks", style="magenta")

    for ak in ["forex", "crypto", "stocks"]:
        row = res.correlation_matrix.get(ak, {})
        corr_table.add_row(
            ak.upper(),
            f"{row.get('forex', 0.0):+.3f}",
            f"{row.get('crypto', 0.0):+.3f}",
            f"{row.get('stocks', 0.0):+.3f}",
        )
    console.print(corr_table)

    if export_csv:
        res.equity_curve.to_csv(export_csv, index=False)
        console.print(f"[green]Saved daily equity curve to {export_csv}[/green]")


@app.command(name="risk-status")

def risk_status() -> None:
    """Inspect the current state and capital drawdowns of the DareFX Circuit Breaker."""
    from darefx.risk.circuit_breaker import CircuitBreaker, CircuitState

    cb = CircuitBreaker()
    status = cb.update(current_equity=cb.current_equity, current_date_str=cb.last_trade_date or "N/A")

    state_color = "green" if status.state == CircuitState.ACTIVE else "yellow" if status.state == CircuitState.PAUSED_DAILY else "red"

    table = Table(title="DareFX Circuit Breaker Capital Protection Status")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="bold white")

    table.add_row("Circuit State", f"[{state_color}]{status.state.value}[/{state_color}]")
    table.add_row("Current Equity", f"${status.current_equity:,.2f}")
    table.add_row("Peak Equity", f"${status.peak_equity:,.2f}")
    table.add_row("Daily Open Equity", f"${status.daily_open_equity:,.2f}")
    table.add_row("Daily P&L %", f"{status.daily_pnl_pct:+.2f}%")
    table.add_row("Peak Drawdown %", f"{status.peak_drawdown_pct:.2f}%")
    table.add_row("Active Reason / Note", status.reason)

    console.print(table)


@app.command(name="reset-shutdown")
def reset_shutdown() -> None:
    """Manually clear SHUTDOWN state and restore Circuit Breaker to ACTIVE."""
    from darefx.risk.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker()
    cb.reset_shutdown()
    console.print("[bold green]Circuit Breaker successfully reset to ACTIVE state.[/bold green]")


@app.command(name="evaluate")
def evaluate(
    symbol: str = typer.Option("EURUSD", help="Currency pair"),
    trades_file: str = typer.Option("data/processed/eurusd_backtest_trades.csv", help="Path to backtest trades CSV"),
    paper_trades_file: str = typer.Option("", help="Optional path to MT5 paper trades CSV"),
    trials: int = typer.Option(35, help="Number of model optimization trials"),
    output_report: str = typer.Option("docs/EVALUATION-REPORT.md", help="Destination markdown report file"),
) -> None:
    """Run Deflated Sharpe Ratio (DSR) analysis and generate Phase 5 Go/No-Go Decision Report."""
    import pandas as pd

    from darefx.analysis.evaluator import DecisionRecommendation, SystemEvaluator

    t_path = Path(trades_file)
    if not t_path.exists():
        console.print(f"[red]Trades file not found at {t_path}. Run 'darefx backtest' or 'darefx tune' first.[/red]")
        return

    console.print(f"[bold cyan]Running Phase 5 Statistical Significance and Go/No-Go Evaluation for {symbol}...[/bold cyan]")
    df_trades = pd.read_csv(t_path)

    df_paper = pd.read_csv(paper_trades_file) if paper_trades_file and Path(paper_trades_file).exists() else None

    evaluator = SystemEvaluator()
    outcome = evaluator.evaluate(trades_df=df_trades, paper_trades_df=df_paper, num_trials=trials)
    report_content = evaluator.generate_report_markdown(outcome, output_file=output_report)

    rec = outcome.recommendation
    rec_style = "bold green" if rec == DecisionRecommendation.GO else "bold yellow" if rec == DecisionRecommendation.ITERATE else "bold red"

    console.print(f"\n[bold white]========== PHASE 5 VERDICT: [{rec_style}]{rec.value}[/{rec_style}] (Confidence: {outcome.confidence_pct:.1f}%) ==========[/bold white]\n")

    table = Table(title="Institutional Statistical Verification Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold white")
    table.add_column("Institutional Criterion", style="yellow")
    table.add_column("Verdict", style="white")

    verdict_sharpe = "PASS" if outcome.dsr_result.annualized_sharpe >= 0.50 else "FAIL"
    verdict_psr = "PASS" if outcome.dsr_result.psr >= 0.95 else "FAIL"
    verdict_dsr = "PASS" if outcome.dsr_result.dsr >= 0.50 else "FAIL"
    verdict_dd = "PASS" if outcome.metrics.max_drawdown_pct <= 15.0 else "FAIL"
    verdict_slip = "PASS" if not outcome.reconciliation.slippage.violates_assumption else "FAIL"

    table.add_row("Annualized Sharpe Ratio", f"{outcome.dsr_result.annualized_sharpe:.2f}", "> 0.50 (Phase 3 Gate)", f"[{'green' if verdict_sharpe == 'PASS' else 'red'}]{verdict_sharpe}[/]")
    table.add_row("Probabilistic Sharpe Ratio (PSR)", f"{outcome.dsr_result.psr * 100:.1f}%", "> 95.0% (5% Significance)", f"[{'green' if verdict_psr == 'PASS' else 'red'}]{verdict_psr}[/]")
    table.add_row("Deflated Sharpe Ratio (DSR)", f"{outcome.dsr_result.dsr * 100:.1f}%", f"> 50.0% ({trials} trials)", f"[{'green' if verdict_dsr == 'PASS' else 'red'}]{verdict_dsr}[/]")
    table.add_row("Return Skewness", f"{outcome.dsr_result.skewness:.3f}", "Asymmetric upside", "INFO")
    table.add_row("Pearson Kurtosis", f"{outcome.dsr_result.kurtosis:.3f}", "Fat-tail leptokurtic (> 3.0)", "INFO")
    table.add_row("Maximum Drawdown", f"{outcome.metrics.max_drawdown_pct:.2f}%", "< 15.00%", f"[{'green' if verdict_dd == 'PASS' else 'red'}]{verdict_dd}[/]")
    table.add_row("Mean Execution Slippage", f"{outcome.reconciliation.slippage.mean_slippage_pips:.2f} pips", "<= 1.00 pip assumption", f"[{'green' if verdict_slip == 'PASS' else 'red'}]{verdict_slip}[/]")

    console.print(table)
    console.print(f"\nSaved comprehensive evaluation report to: [bold green]{output_report}[/bold green]")


@app.command(name="analyze")
def analyze(
    symbol: str = typer.Option("EURUSD", help="Currency pair (e.g. EURUSD)"),
    equity: float = typer.Option(10_000.0, help="Account equity for lot sizing"),
    live: bool = typer.Option(True, "--live/--no-live", help="Fetch fresh live market data from Yahoo Finance"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON data"),
) -> None:
    """Run comprehensive AI market analysis and generate Buy/Sell recommendations."""
    import json

    from darefx.analysis.market_analyzer import MarketAnalyzer

    console.print(f"[bold cyan]Initiating DareFX AI Market Analysis for {symbol}...[/bold cyan]")
    analyzer = MarketAnalyzer(symbol=symbol)
    try:
        report = analyzer.analyze(account_equity=equity, fetch_live=live)
    except Exception as err:
        console.print(f"[red]Analysis failed: {err}[/red]")
        return

    if json_output:
        console.print_json(json.dumps(report.to_dict()))
        return

    table = Table(title=f"DareFX AI Market Diagnosis & Trade Plan: {symbol}")
    table.add_column("Parameter / Indicator", style="cyan")
    table.add_column("Current Value", style="bold white")
    table.add_column("Diagnosis / Interpretation", style="yellow")

    table.add_row("Current Price", f"{report.current_price:.5f}", f"{report.price_change_pips:+.1f} pips ({report.price_change_pct:+.2f}%)")
    table.add_row("Day Range", f"{report.low_price:.5f} - {report.high_price:.5f}", "Daily Low - High")
    table.add_row("Trend Structure", report.trend_bias, f"EMA 9={report.ema_9:.5f}, 21={report.ema_21:.5f}, 50={report.ema_50:.5f}, 200={report.ema_200:.5f}")
    table.add_row("ADX (14) Trend Strength", f"{report.adx_14:.1f}", report.adx_condition)
    table.add_row("RSI (14) Momentum", f"{report.rsi_14:.1f}", report.rsi_condition)
    table.add_row("MACD Histogram", f"{report.macd_hist:+.5f}", report.macd_condition)
    table.add_row("ATR (14) Daily Volatility", f"{report.atr_pips:.1f} pips", "Expected daily move")
    table.add_row("Bollinger Range", f"{report.bb_lower:.5f} - {report.bb_upper:.5f}", f"Mid: {report.bb_middle:.5f}")

    table.add_row("ML Prob: Buy (+1)", f"{report.prob_buy * 100:.1f}%", "LightGBM Profit Barrier Target")
    table.add_row("ML Prob: Neutral (0)", f"{report.prob_neutral * 100:.1f}%", "LightGBM Vertical Expiry")
    table.add_row("ML Prob: Sell (-1)", f"{report.prob_sell * 100:.1f}%", "LightGBM Stop Loss Target")

    rec_color = "green" if report.recommendation == "BUY" else "red" if report.recommendation == "SELL" else "white"
    table.add_row("AI Recommendation", f"[{rec_color}]{report.recommendation_title}[/{rec_color}]", report.reasoning)

    if report.recommendation in ("BUY", "SELL"):
        table.add_row("Planned Entry", f"{report.entry_price:.5f}", "Market order")
        table.add_row("Stop Loss (SL)", f"{report.stop_loss:.5f}", f"{report.stop_pips:.1f} pips risk")
        table.add_row("Take Profit (TP)", f"{report.take_profit:.5f}", f"{report.target_pips:.1f} pips target")
        table.add_row("Risk / Reward Ratio", f"1 : {report.risk_reward_ratio:.1f}", "Asymmetric edge")
        table.add_row("Recommended Sizing", f"{report.recommended_lots:.2f} lots", f"1.0% risk on ${equity:,.2f}")

    console.print(table)


@app.command(name="telegram-bot")
def telegram_bot() -> None:
    """Start the interactive Telegram Control Server listening for mobile commands and button taps."""
    from darefx.notifications.telegram_server import TelegramServer

    console.print("[bold cyan]Starting DareFX Interactive Telegram Control Server...[/bold cyan]")
    server = TelegramServer()
    if not server.bot_token or not server.allowed_chat_id:
        console.print("[red]Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env[/red]")
        return

    console.print(f"[bold green]Connected! Listening for commands from Telegram Chat ID: {server.allowed_chat_id}[/bold green]")
    console.print("[yellow]Press Ctrl+C to stop.[/yellow]")
    try:
        server.start_polling()
    except KeyboardInterrupt:
        console.print("[cyan]Telegram bot server stopped.[/cyan]")


@app.command(name="web")
def web_cockpit(
    host: str = typer.Option("0.0.0.0", help="HTTP binding host"),
    port: int = typer.Option(8888, help="HTTP listening port"),
) -> None:
    """Launch DareFX Mobile Web Cockpit for browser and Tailscale remote access."""
    import asyncio

    from darefx.trading.multi_scheduler import MultiScheduler
    from darefx.web.server import WebCockpitServer, get_tailscale_ip

    ts_ip = get_tailscale_ip()
    console.print(f"[bold cyan]Starting DareFX Mobile Web Cockpit on {host}:{port}...[/bold cyan]")
    console.print(f"[bold green]Local access:      http://127.0.0.1:{port}[/bold green]")
    console.print(f"[bold blue]Tailscale access:  http://{ts_ip}:{port}[/bold blue]")
    console.print("[yellow]Press Ctrl+C to terminate.[/yellow]")

    scheduler = MultiScheduler()
    server = WebCockpitServer(host=host, port=port, scheduler=scheduler)

    async def _main() -> None:
        await server.start()
        try:
            while True:
                await asyncio.sleep(1.0)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await server.stop()

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        console.print("[cyan]Web cockpit safely stopped.[/cyan]")


# ---------------------------------------------------------------------------
# Daemon Management CLI
# ---------------------------------------------------------------------------
daemon_app = typer.Typer(help="24/7 Production Daemon orchestration")
app.add_typer(daemon_app, name="daemon")


@daemon_app.command(name="start")
def daemon_start(
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run daemon in foreground"),
    port: int = typer.Option(8888, help="Web Cockpit listening port"),
) -> None:
    """Start 24/7 multi-asset trading daemon."""
    import subprocess
    import sys

    from darefx.trading.daemon import DaemonConfig, DareFXDaemon

    cfg = DaemonConfig(web_port=port)
    daemon = DareFXDaemon(config=cfg)

    existing_pid = daemon.get_running_pid()
    if existing_pid:
        console.print(f"[yellow]DareFX Daemon is already running (PID {existing_pid}).[/yellow]")
        return

    if foreground:
        console.print("[bold cyan]Launching DareFX 24/7 Daemon in foreground...[/bold cyan]")
        daemon.start_foreground()
    else:
        console.print(
            "[bold cyan]Launching DareFX 24/7 Daemon in detached background mode...[/bold cyan]"
        )
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "darefx.cli",
                "daemon",
                "start",
                "--foreground",
                "--port",
                str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        console.print(f"[bold green]DareFX Daemon spawned with PID {proc.pid}.[/bold green]")
        console.print("Check status with: [cyan]darefx daemon status[/cyan]")


@daemon_app.command(name="stop")
def daemon_stop() -> None:
    """Stop running 24/7 trading daemon."""
    from darefx.trading.daemon import DareFXDaemon

    daemon = DareFXDaemon()
    pid = daemon.get_running_pid()
    if not pid:
        console.print("[yellow]No active DareFX Daemon detected.[/yellow]")
        return

    console.print(f"[cyan]Stopping DareFX Daemon (PID {pid})...[/cyan]")
    ok = daemon.stop_process()
    if ok:
        console.print("[bold green]DareFX Daemon stopped successfully.[/bold green]")
    else:
        console.print("[red]Failed to stop daemon process.[/red]")


@daemon_app.command(name="status")
def daemon_status() -> None:
    """Check status of 24/7 trading daemon."""
    from darefx.trading.daemon import DareFXDaemon

    daemon = DareFXDaemon()
    st = daemon.get_status()

    table = Table(title="DareFX 24/7 Daemon Status")
    table.add_column("Property", style="white")
    table.add_column("Value", style="bold green")

    if st.get("running"):
        table.add_row("Status", "[bold green]ONLINE (RUNNING)[/bold green]")
        table.add_row("Process ID (PID)", str(st.get("pid")))
        table.add_row("Uptime", f"{st.get('uptime_sec', 0)} seconds")
        table.add_row("Memory RSS", f"{st.get('memory_mb', 0)} MB")
        table.add_row("Open Positions", str(st.get("open_positions", 0)))
        table.add_row("Tailscale Endpoint", f"http://{st.get('tailscale_ip')}:8888")
    else:
        table.add_row("Status", "[bold red]OFFLINE (STOPPED)[/bold red]")
        table.add_row("PID", "None")

    console.print(table)


# ---------------------------------------------------------------------------
# Systemd Service Management CLI
# ---------------------------------------------------------------------------
service_app = typer.Typer(help="systemd service installation and management")
app.add_typer(service_app, name="service")


@service_app.command(name="install")
def service_install(
    user: bool = typer.Option(
        True, help="Install as rootless user service (~/.config/systemd/user)"
    ),
    port: int = typer.Option(8888, help="Web Cockpit listening port"),
) -> None:
    """Install and enable DareFX systemd service."""
    from darefx.trading.daemon import install_systemd_service

    try:
        path = install_systemd_service(user_mode=user, port=port)
        console.print(f"[bold green]Installed and enabled systemd service: {path}[/bold green]")
        console.print("Start service now with: [cyan]darefx service start[/cyan]")
    except Exception as err:
        console.print(f"[red]Failed installing service: {err}[/red]")


@service_app.command(name="uninstall")
def service_uninstall(
    user: bool = typer.Option(True, help="Uninstall user service"),
) -> None:
    """Disable and uninstall DareFX systemd service."""
    from darefx.trading.daemon import uninstall_systemd_service

    ok = uninstall_systemd_service(user_mode=user)
    if ok:
        console.print("[green]DareFX systemd service disabled and removed.[/green]")
    else:
        console.print("[red]Failed to uninstall systemd service.[/red]")


@service_app.command(name="status")
def service_status_cmd(
    user: bool = typer.Option(True, help="Check user service"),
) -> None:
    """Check systemctl status of darefx.service."""
    from darefx.trading.daemon import run_service_command

    code, out = run_service_command("status", user_mode=user)
    color = "green" if code == 0 else "yellow"
    console.print(f"[{color}]{out}[/{color}]")


@service_app.command(name="start")
def service_start_cmd(user: bool = typer.Option(True, help="Start user service")) -> None:
    """Start darefx.service via systemctl."""
    from darefx.trading.daemon import run_service_command

    code, out = run_service_command("start", user_mode=user)
    if code == 0:
        console.print("[green]DareFX service started.[/green]")
    else:
        console.print(f"[red]Error: {out}[/red]")


@service_app.command(name="stop")
def service_stop_cmd(user: bool = typer.Option(True, help="Stop user service")) -> None:
    """Stop darefx.service via systemctl."""
    from darefx.trading.daemon import run_service_command

    code, out = run_service_command("stop", user_mode=user)
    if code == 0:
        console.print("[green]DareFX service stopped.[/green]")
    else:
        console.print(f"[red]Error: {out}[/red]")


@service_app.command(name="restart")
def service_restart_cmd(user: bool = typer.Option(True, help="Restart user service")) -> None:
    """Restart darefx.service via systemctl."""
    from darefx.trading.daemon import run_service_command

    code, out = run_service_command("restart", user_mode=user)
    if code == 0:
        console.print("[green]DareFX service restarted.[/green]")
    else:
        console.print(f"[red]Error: {out}[/red]")


if __name__ == "__main__":
    app()





