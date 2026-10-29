"""Generate a high-resolution dark-themed architecture flowchart for DareFX."""

import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig = plt.figure(figsize=(16, 10), dpi=300)
ax = fig.add_subplot(111)
ax.set_facecolor("#0b0f19")
fig.patch.set_facecolor("#0b0f19")

# Helper function to draw rounded stylized card
def draw_card(ax, x, y, w, h, title, subtitle, items, border_color="#30363d", bg_color="#161b22", title_color="#58a6ff"):
    rect = patches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.03",
        linewidth=1.8,
        edgecolor=border_color,
        facecolor=bg_color,
        zorder=2
    )
    ax.add_patch(rect)
    
    # Title
    ax.text(x + 0.03, y + h - 0.05, title, fontsize=12, fontweight="bold", color=title_color, family="sans-serif", zorder=3)
    if subtitle:
        ax.text(x + 0.03, y + h - 0.08, subtitle, fontsize=8.5, color="#8b949e", style="italic", family="sans-serif", zorder=3)
        start_y = y + h - 0.13
    else:
        start_y = y + h - 0.10

    # Bullet items
    line_spacing = 0.038
    for i, item in enumerate(items):
        ax.text(x + 0.03, start_y - (i * line_spacing), f"• {item}", fontsize=9, color="#c9d1d9", family="sans-serif", zorder=3)

# Helper function for arrow
def draw_arrow(ax, start, end, color="#58a6ff", style="->", lw=2.2):
    ax.annotate(
        "",
        xy=end, xycoords="data",
        xytext=start, textcoords="data",
        arrowprops=dict(arrowstyle=style, color=color, lw=lw, shrinkA=4, shrinkB=4, mutation_scale=15),
        zorder=4
    )

# Header Title
ax.text(0.5, 0.96, "DAREFX — END-TO-END SYSTEM ARCHITECTURE", fontsize=18, fontweight="bold", color="#ffffff", ha="center", family="sans-serif")
ax.text(0.5, 0.93, "Autonomous Institutional Machine Learning Auto-Trading Engine for EUR/USD D1", fontsize=10.5, color="#8b949e", ha="center", family="sans-serif")

# Row 1: Pipeline
# Box 1: Scheduler & Data Ingestion
draw_card(
    ax, 0.04, 0.58, 0.26, 0.30,
    "1. INGESTION & DATA FEED",
    "Scheduled Daily 22:05 UTC (05:05 WIB)",
    [
        "Systemd User Daemon Timer",
        "Yahoo Finance / Dukascopy bi5",
        "NY 17:00 EST Close Alignment",
        "Tick Cleaner & Outlier Filter",
        "Snappy Parquet Partitioning"
    ],
    border_color="#388bfd", bg_color="#121d2f", title_color="#58a6ff"
)

# Box 2: Feature Engineering & Labeling
draw_card(
    ax, 0.37, 0.58, 0.26, 0.30,
    "2. FEATURES & LABELS",
    "Marcos López de Prado (2014) Method",
    [
        "35 Stationary Indicators (RSI, ADX, MACD)",
        "Bollinger Bands, ATR, EMA 9-200 Ratios",
        "Backward-Looking Z-Score Scaling",
        "Zero Forward Look-Ahead Bias",
        "Triple Barrier (+1 PT, -1 SL, 0 Time)"
    ],
    border_color="#7ee787", bg_color="#11271d", title_color="#7ee787"
)

# Box 3: Model & Regime Filter
draw_card(
    ax, 0.70, 0.58, 0.26, 0.30,
    "3. MACHINE LEARNING & REGIME",
    "79-Fold Purged Walk-Forward Cross-Validation",
    [
        "LightGBM & XGBoost Classifiers",
        "Combinatorial Purged CV (CPCV)",
        "10-Day Purge Gap + 5-Day Embargo",
        "Bayesian Optuna Policy Tuner",
        "Trend Regime Gate (ADX >= 32.0)"
    ],
    border_color="#d2a8ff", bg_color="#211833", title_color="#d2a8ff"
)

# Row 2: Risk Management, Execution, and Mobile Control
# Box 4: Risk Management & Circuit Breaker
draw_card(
    ax, 0.04, 0.12, 0.40, 0.36,
    "4. CAPITAL PROTECTION & RISK CONTROL",
    "Layered Institutional Defense Invariants",
    [
        "Fixed Fractional Position Sizing (1.0% Risk Cap)",
        "Half-Kelly Scaling Bounded by 5% Margin Ceiling",
        "Standard Lot Quantization (0.01 Micro-Lot Step)",
        "Circuit Breaker FSM State Machine:",
        "  • ACTIVE: Unrestricted daily operations",
        "  • PAUSED_DAILY: Auto-halt at -5.0% daily equity loss",
        "  • SHUTDOWN: Total lock at -15.0% peak drawdown",
        "Single Concurrent Position Constraint (No Martingale)"
    ],
    border_color="#f85149", bg_color="#2b1518", title_color="#ff7b72"
)

# Box 5: MT5 Bridge & Telegram Control
draw_card(
    ax, 0.52, 0.12, 0.44, 0.36,
    "5. BROKER EXECUTION & MOBILE CONTROL",
    "Autonomous Execution & Real-Time Monitoring",
    [
        "Dual MetaTrader 5 Bridge Adapter:",
        "  • Native Linux Paper/Simulation Mode",
        "  • Direct Valetax MT5 Broker Terminal Bridge",
        "Pre-Trade Spread Sanity Guard (< 3.0 Pips)",
        "Automatic Hard SL & TP Bracket Placement",
        "Interactive Telegram Server (@darefxbot):",
        "  • Instant Mobile Signal & Execution Alerts",
        "  • 6 Quick Tap Buttons (/status, /check, /run)",
        "Deflated Sharpe Ratio (DSR 91.9%, PSR 98.6%)"
    ],
    border_color="#f0883e", bg_color="#271d15", title_color="#ffa657"
)

# Connecting Arrows
# Ingestion -> Features
draw_arrow(ax, (0.30, 0.73), (0.37, 0.73), color="#388bfd")
# Features -> Model
draw_arrow(ax, (0.63, 0.73), (0.70, 0.73), color="#7ee787")
# Model -> Risk (downwards)
draw_arrow(ax, (0.83, 0.58), (0.83, 0.52), color="#d2a8ff")
draw_arrow(ax, (0.83, 0.52), (0.24, 0.52), color="#d2a8ff")
draw_arrow(ax, (0.24, 0.52), (0.24, 0.48), color="#ff7b72")
# Risk -> Execution
draw_arrow(ax, (0.44, 0.30), (0.52, 0.30), color="#f0883e")

# Footer metadata
ax.text(0.5, 0.04, "DareFX Architecture • Marcos López de Prado Quant Framework • Valetax MT5 Supported • Verified with 46 Unit Tests", fontsize=8.5, color="#6e7681", ha="center", family="sans-serif")

ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

plt.tight_layout()
output_path = "docs/assets/architecture_flowchart.png"
plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")
print(f"Successfully generated {output_path}")
