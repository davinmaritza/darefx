# DareFX — Production Deployment & Operator Runbook

This runbook guides the human operator through deploying, configuring, and monitoring DareFX. Under the autonomous operating model, **the human operator is only responsible for broker deposits and capital allocations**; DareFX autonomously executes 100% of data ingestion, feature extraction, model inference, risk sizing, MT5 order dispatching, and protective exits.

---

## 1. Prerequisites & Environment Setup

### System Requirements
- OS: Linux Mint, Ubuntu 22.04+, or Debian 12 (Local host or Cloud VPS).
- Python: 3.12+ (isolated via `.venv`).
- Package Manager: `uv` (recommended) or `pip`.

### Dependency Installation
```bash
cd /path/to/darefx
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

---

## 2. Broker & Telegram Configuration (`.env`)

Create `.env` in the project root:
```ini
# MetaTrader 5 Broker Configuration (Valetax)
MT5_LOGIN=12345678
MT5_PASSWORD="YourBrokerInvestorOrMasterPassword"
MT5_SERVER="Valetax-Live"   # or "Valetax-Demo"
MT5_SIMULATION="false"      # Set to "true" for offline dry-run mode

# Telegram Notification Bot
TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_CHAT_ID="987654321"

# Operational Risk Controls
MAX_DAILY_LOSS_PCT=5.0
MAX_DRAWDOWN_PCT=15.0
```

---

## 3. Autonomous Daemon Setup (Systemd)

DareFX executes once daily at **22:05 UTC** (05:05 WIB), 5 minutes after the daily 17:00 New York EST candle closes.

### Enable User Service & Timer
```bash
# 1. Create user systemd directory if not exists
mkdir -p ~/.config/systemd/user

# 2. Copy unit files
cp scripts/darefx.service ~/.config/systemd/user/
cp scripts/darefx.timer ~/.config/systemd/user/

# 3. Reload systemd and enable timer
systemctl --user daemon-reload
systemctl --user enable --now darefx.timer

# 4. Enable lingering so user services run even when logged out
loginctl enable-linger $USER
```

### Verify Schedule
```bash
systemctl --user list-timers --all | grep darefx
```

---

## 4. Daily Monitoring & Operational Commands

### Live Risk & Circuit Breaker Status
```bash
darefx risk-status
```
Outputs current circuit state (`ACTIVE`, `PAUSED_DAILY`, or `SHUTDOWN`), equity, daily P&L, and peak drawdown.

### Manual On-Demand Cycle Run
```bash
darefx run-cycle --equity 10000 --execute
```

### Inspect Execution Logs
```bash
# View last 100 lines of systemd execution journal
journalctl --user -u darefx.service -n 100 --no-pager

# Follow logs in real time
journalctl --user -u darefx.service -f
```

---

## 5. Statistical Auditing & Go/No-Go Decision

To audit the trading history and verify mathematical edge against multiple testing:
```bash
darefx evaluate
```
Generates `docs/EVALUATION-REPORT.md` containing Deflated Sharpe Ratio, Probabilistic Sharpe Ratio, and empirical slippage statistics.

---

## 6. Emergency Procedures

### Scenario A: Circuit Breaker Reaches `PAUSED_DAILY` (-5.0% daily loss)
- **Automatic Behavior:** New trade entries are blocked until the next daily candle rollover at 00:00 UTC.
- **Action Required:** None; system automatically resets to `ACTIVE` the following day.

### Scenario B: Circuit Breaker Reaches `SHUTDOWN` (-15.0% peak drawdown)
- **Automatic Behavior:** All trading is halted permanently. Telegram sends an emergency alert.
- **Operator Action:**
  1. Review broker equity and open positions in MT5.
  2. Inspect logs: `journalctl --user -u darefx.service -n 200`.
  3. Once root cause is resolved, manually clear the shutdown:
     ```bash
     darefx reset-shutdown
     ```

### Scenario C: Complete Manual Disconnect
```bash
systemctl --user stop darefx.timer
systemctl --user disable darefx.timer
```
Existing open positions in MT5 will maintain their hard Stop Loss and Take Profit orders managed by the broker.
