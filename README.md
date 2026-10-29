# DareFX

AI-powered EUR/USD forex auto-trading bot. LightGBM/XGBoost classifier with triple barrier labeling, walk-forward validation, layered risk management, and Telegram monitoring.

**Status**: Documentation & architecture phase. No trading code yet.

## What this is

A supervised ML system that predicts EUR/USD daily direction, sizes positions using Kelly criterion with circuit breakers, and executes through MetaTrader 5 on a Valetax demo account.

## What this is not

- Not a get-rich-quick scheme. Target: beat S&P500 annual return (~10%), which most hedge funds fail to do consistently.
- Not HFT. Daily timeframe, swing trading.
- Not a SaaS product. Personal use.

## Docs

| Document | Purpose |
|----------|---------|
| [FOREX-101](docs/FOREX-101.md) | Forex mechanics crash course |
| [PRD](docs/PRD.md) | Product requirements |
| [SRS](docs/SRS.md) | Software requirements specification |
| [Architecture](docs/ARCHITECTURE.md) | System design and component diagram |
| [Data Pipeline](docs/DATA-PIPELINE.md) | Data sourcing, cleaning, feature engineering |
| [Risk Management](docs/RISK-MANAGEMENT.md) | Position sizing and circuit breakers |
| [Roadmap](docs/ROADMAP.md) | 6-month phased development plan |
| [TODO](docs/TODO.md) | Task checklist |

## Quick Start

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

## License

MIT
