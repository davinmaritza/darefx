#!/usr/bin/env bash
set -euo pipefail

# DareFX Daily Automated Trading Cycle Runner
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Source virtual environment
source .venv/bin/activate

echo "[$(date -u --iso-8601=seconds)] Running DareFX Daily Cycle..."

# 1. Fetch latest daily candle
darefx fetch --source yahoo --symbol EURUSD --range-str 5y

# 2. Run analysis, circuit breaker check, sizing, execution, and alert
darefx run-cycle --symbol EURUSD --equity 10000.0 --threshold 0.46 --adx-min 32.0 --execute

echo "[$(date -u --iso-8601=seconds)] DareFX Daily Cycle Complete."
