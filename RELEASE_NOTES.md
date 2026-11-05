# DareFX v1.0.0

DareFX v1.0.0 is the initial stable release of the automated EUR/USD trading terminal and ML execution engine.

---

### Highlights

#### Desktop Terminal (PySide6 / Qt)
- Account summary cards showing balance, equity, margin utilization, and floating profit/loss
- Active positions table with dynamic break-even indicators and individual close buttons
- Controls for auto-trade toggle, emergency close all, manual orders, and on-demand model inference
- System tray minimization to keep trading active in the background
- Multi-resolution app icon and Windows desktop shortcuts

#### Signal Engine & Validation
- Walk-forward LightGBM models trained on 25 years of daily EUR/USD data
- Triple-barrier labeling with ATR-scaled take profit and stop loss targets
- 79 walk-forward folds with a 10-day purge gap and 5-day embargo to eliminate leakage
- 35 stationary indicators normalized with rolling backward-looking z-scores
- 2007–2026 walk-forward audit results:
  - Total Net Return: +37.58% ($10,000 → $13,757)
  - Annualized Sharpe Ratio: 4.24
  - Deflated Sharpe Ratio (DSR): 98.2% across 35 optimization trials
  - Max Drawdown: 4.62%
  - Win Rate: 59.02% (72 wins / 50 losses)

#### Risk Management
- Fixed fractional position sizing (1.0% risk per trade) capped by half-Kelly constraints
- Automated break-even protection (+1.5 pips profit lock once trades advance +15 pips)
- Economic news filter via ForexFactory to freeze trading around high-impact events
- Circuit breaker state machine to halt trading if daily loss hits -5.0% or total drawdown exceeds -15.0%

#### Telegram Server
- Remote status monitoring and trade commands (`/status`, `/analisis`, `/news`, `/breakeven`, `/closeall`)
- Real-time order execution and safety halt notifications

---

### Pre-compiled Binaries & Installers

Standalone desktop binaries and installers are attached directly to this release:

| Platform | Format | Filename | Size | Details |
| :--- | :--- | :--- | :--- | :--- |
| Windows (x86_64) | Standalone Executable | [`DareFX-windows-x86_64.exe`](https://github.com/davinmaritza/darefx/releases/download/v1.0.0/DareFX-windows-x86_64.exe) | 186 MB | Portable Windows executable with MetaTrader 5 API support |
| Linux (Debian / Ubuntu / Mint) | Debian Package | [`darefx_1.0.0_amd64.deb`](https://github.com/davinmaritza/darefx/releases/download/v1.0.0/darefx_1.0.0_amd64.deb) | 526 MB | Installs system application entry and desktop launcher |
| Linux (Generic x86_64) | Tarball Archive | [`DareFX-linux-x86_64.tar.gz`](https://github.com/davinmaritza/darefx/releases/download/v1.0.0/DareFX-linux-x86_64.tar.gz) | 534 MB | Self-contained portable executable bundle |

#### Running the Binaries
```bash
# Windows
# Download DareFX-windows-x86_64.exe and double-click to run

# Linux (Debian / Ubuntu / Mint)
sudo dpkg -i darefx_1.0.0_amd64.deb
darefx-gui

# Linux (Portable Archive)
tar -xzf DareFX-linux-x86_64.tar.gz
./DareFX
```

---

### Running from Source

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
```
