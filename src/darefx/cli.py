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


if __name__ == "__main__":
    app()

