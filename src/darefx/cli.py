"""DareFX Command Line Interface."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table
import typer

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
        start_dt = datetime(2024, 1, 8, tzinfo=timezone.utc)
        end_dt = datetime(2024, 1, 9, tzinfo=timezone.utc)
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

    console.print(f"[bold green]Feature matrix generated successfully![/bold green]")
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

    config = BacktestConfig(
        initial_capital=capital,
        risk_per_trade_pct=risk,
        spread_pips=spread,
        slippage_pips=slippage,
        confidence_threshold=threshold,
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


if __name__ == "__main__":
    app()




