"""Generate an institutional, agency-grade architecture flowchart for DareFX.

Eliminates AI-slop hallmarks:
- Replaces chaotic rainbow boxes with an elegant, monochromatic dark slate design and subtle semantic accents.
- Uses a clean, left-to-right 5-stage pipeline without awkward zigzagging arrows.
- Organizes content into structured key-value specifications rather than walls of bullet text.
- Eliminates all text clipping and overlapping.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as patches


def create_flowchart(output_path: str = "docs/assets/architecture_flowchart.png") -> None:
    # 16:9 high-definition canvas
    fig = plt.figure(figsize=(19.2, 10.8), dpi=300)
    ax = fig.add_subplot(111)

    # Dark institutional slate background
    bg_color = "#070a12"
    ax.set_facecolor(bg_color)
    fig.patch.set_facecolor(bg_color)

    # Subtle background technical grid
    for x_grid in [i * 0.05 for i in range(21)]:
        ax.axvline(x_grid, color="#121826", lw=0.6, zorder=0, alpha=0.5)
    for y_grid in [i * 0.05 for i in range(21)]:
        ax.axhline(y_grid, color="#121826", lw=0.6, zorder=0, alpha=0.5)

    # -------------------------------------------------------------
    # 1. TOP HEADER & TELEMETRY BADGES
    # -------------------------------------------------------------
    # Brand Monogram Tag
    ax.text(
        0.030, 0.945,
        "DAREFX QUANTITATIVE ARCHITECTURE",
        fontsize=16,
        fontweight="bold",
        color="#f8fafc",
        family="sans-serif",
        zorder=3
    )
    ax.text(
        0.030, 0.915,
        "Autonomous Machine Learning Trading Engine for EUR/USD D1 • Marcos López de Prado Quant Standard",
        fontsize=10,
        color="#94a3b8",
        family="sans-serif",
        zorder=3
    )

    # System Status Badges (Top Right)
    badges = [
        ("● PRODUCTION READY", "#10b981", "#064e3b"),
        ("DSR: 98.2%", "#38bdf8", "#082f49"),
        ("SHARPE: 4.24", "#a855f7", "#3b0764"),
        ("53/53 TESTS PASS", "#f59e0b", "#451a03"),
    ]
    badge_x = 0.970
    for label, text_color, badge_bg in reversed(badges):
        badge_w = 0.095
        badge_x -= badge_w
        rect = patches.FancyBboxPatch(
            (badge_x, 0.915), badge_w - 0.010, 0.032,
            boxstyle="round,pad=0.006,rounding_size=0.010",
            linewidth=1.0,
            edgecolor=text_color,
            facecolor=badge_bg,
            zorder=3
        )
        ax.add_patch(rect)
        ax.text(
            badge_x + (badge_w - 0.010) / 2, 0.931,
            label,
            fontsize=7.8,
            fontweight="bold",
            color=text_color,
            ha="center",
            va="center",
            family="monospace",
            zorder=4
        )
        badge_x -= 0.008

    # Divider below header
    ax.plot([0.030, 0.970], [0.885, 0.885], color="#1e293b", lw=1.2, zorder=2)

    # -------------------------------------------------------------
    # 2. 5-STAGE PIPELINE CARDS (LEFT-TO-RIGHT UNIDIRECTIONAL FLOW)
    # -------------------------------------------------------------
    stages = [
        {
            "tag": "STAGE 01",
            "title": "DATA INGESTION",
            "subtitle": "Daily Market Synchronization",
            "accent": "#38bdf8",
            "specs": [
                ("Trigger", "Daily 22:05 UTC (NY 17:00 Close)"),
                ("Sources", "Yahoo Finance & Dukascopy bi5"),
                ("Sanitization", "Tick Cleaner & Outlier Detection"),
                ("Resolution", "Daily D1 OHLCV Candle Aggregation"),
                ("Storage Lake", "Snappy Parquet Partitioned Store"),
            ],
            "footer_badge": "ZERO LOOK-AHEAD BIAS",
        },
        {
            "tag": "STAGE 02",
            "title": "FEATURE & LABELS",
            "subtitle": "Stationary Feature Engineering",
            "accent": "#34d399",
            "specs": [
                ("Indicators", "35 Stationary Technical Signals"),
                ("Volatility", "ATR(14), Bollinger Bandwidth"),
                ("Momentum", "RSI(14), MACD Hist, ADX Trend"),
                ("Normalization", "Rolling Backward Z-Score Scaling"),
                ("Labeling", "Triple Barrier (+1 PT, -1 SL, 0 Time)"),
            ],
            "footer_badge": "STATIONARY & NORMALIZED",
        },
        {
            "tag": "STAGE 03",
            "title": "ML ENSEMBLE",
            "subtitle": "Purged Walk-Forward Inference",
            "accent": "#a78bfa",
            "specs": [
                ("Classifiers", "LightGBM & XGBoost Ensemble"),
                ("Validation", "Combinatorial Purged CV (79 Folds)"),
                ("Data Leak Guard", "10-Day Purge Gap + 5-Day Embargo"),
                ("Optimization", "Bayesian Optuna 20-Trial Tuning"),
                ("Regime Filter", "ADX Trend Strength Gate (≥ 32.0)"),
            ],
            "footer_badge": "WIN RATE: 59.02% | PF: 1.72",
        },
        {
            "tag": "STAGE 04",
            "title": "RISK CONTROL",
            "subtitle": "Layered Capital Protection",
            "accent": "#fb7185",
            "specs": [
                ("Capital Cap", "1.0% Fixed Fractional Risk"),
                ("Position Sizing", "Half-Kelly Scale Bounded by 5% Margin"),
                ("Quantization", "0.01 Micro-Lot Step Calibration"),
                ("Circuit Breaker", "PAUSED: -5.0% Daily Loss"),
                ("Max Protection", "SHUTDOWN: -15.0% Peak Drawdown"),
            ],
            "footer_badge": "MAX DRAWDOWN < 4.62%",
        },
        {
            "tag": "STAGE 05",
            "title": "EXECUTION & OPS",
            "subtitle": "Broker Connectivity & Control",
            "accent": "#f59e0b",
            "specs": [
                ("Native Broker", "MetaTrader 5 Direct Terminal Bridge"),
                ("Cloud Gateway", "MetaApi REST/Websocket RPC"),
                ("Execution Guard", "Pre-Trade Max Spread < 3.0 Pips"),
                ("Order Safety", "Automatic Hard SL & TP Brackets"),
                ("Mobile Ops", "Telegram Bot (@darefxbot) Control"),
            ],
            "footer_badge": "VALETAX LIVE-2 COMPATIBLE",
        },
    ]

    card_w = 0.164
    card_gap = 0.027
    start_x = 0.030
    card_y = 0.180
    card_h = 0.675

    card_centers_x = []

    for i, s in enumerate(stages):
        cx = start_x + i * (card_w + card_gap)
        card_centers_x.append(cx + card_w / 2)

        # Base Card Body
        rect = patches.FancyBboxPatch(
            (cx, card_y), card_w, card_h,
            boxstyle="round,pad=0.005,rounding_size=0.015",
            linewidth=1.2,
            edgecolor="#1e293b",
            facecolor="#0b1120",
            zorder=2
        )
        ax.add_patch(rect)

        # Top Accent Strip
        accent_strip = patches.FancyBboxPatch(
            (cx, card_y + card_h - 0.008), card_w, 0.008,
            boxstyle="round,pad=0.001,rounding_size=0.004",
            linewidth=0,
            edgecolor="none",
            facecolor=s["accent"],
            zorder=3
        )
        ax.add_patch(accent_strip)

        # Stage Tag Pill
        tag_rect = patches.FancyBboxPatch(
            (cx + 0.012, card_y + card_h - 0.045), 0.060, 0.022,
            boxstyle="round,pad=0.003,rounding_size=0.006",
            linewidth=0.8,
            edgecolor=s["accent"],
            facecolor="#0f172a",
            zorder=3
        )
        ax.add_patch(tag_rect)
        ax.text(
            cx + 0.042, card_y + card_h - 0.034,
            s["tag"],
            fontsize=7.2,
            fontweight="bold",
            color=s["accent"],
            ha="center",
            va="center",
            family="monospace",
            zorder=4
        )

        # Card Title & Subtitle
        ax.text(
            cx + 0.012, card_y + card_h - 0.075,
            s["title"],
            fontsize=11.5,
            fontweight="bold",
            color="#f8fafc",
            family="sans-serif",
            zorder=3
        )
        ax.text(
            cx + 0.012, card_y + card_h - 0.098,
            s["subtitle"],
            fontsize=7.8,
            color="#94a3b8",
            family="sans-serif",
            zorder=3
        )

        # Horizontal separator inside card
        ax.plot(
            [cx + 0.012, cx + card_w - 0.012],
            [card_y + card_h - 0.115, card_y + card_h - 0.115],
            color="#1e293b",
            lw=0.8,
            zorder=3
        )

        # Structured Specification Items (Key-Value)
        item_y = card_y + card_h - 0.155
        for label, val in s["specs"]:
            # Category label
            ax.text(
                cx + 0.012, item_y,
                label.upper(),
                fontsize=7.0,
                fontweight="bold",
                color=s["accent"],
                family="monospace",
                zorder=3
            )
            # Detail value
            ax.text(
                cx + 0.012, item_y - 0.028,
                val,
                fontsize=7.9,
                color="#e2e8f0",
                family="sans-serif",
                zorder=3
            )
            item_y -= 0.082

        # Card Footer Badge
        fbadge_rect = patches.FancyBboxPatch(
            (cx + 0.010, card_y + 0.018), card_w - 0.020, 0.038,
            boxstyle="round,pad=0.004,rounding_size=0.008",
            linewidth=0.8,
            edgecolor="#334155",
            facecolor="#0f172a",
            zorder=3
        )
        ax.add_patch(fbadge_rect)
        ax.text(
            cx + card_w / 2, card_y + 0.037,
            s["footer_badge"],
            fontsize=7.5,
            fontweight="bold",
            color="#cbd5e1",
            ha="center",
            va="center",
            family="monospace",
            zorder=4
        )

    # -------------------------------------------------------------
    # 3. INTER-STAGE PIPELINE CONNECTORS
    # -------------------------------------------------------------
    connector_labels = [
        "OHLCV BARS",
        "FEATURES",
        "SIGNALS",
        "SIZED LOTS",
    ]
    connector_y = card_y + card_h / 2

    for i in range(4):
        x_from = start_x + i * (card_w + card_gap) + card_w
        x_to = x_from + card_gap

        # Connecting arrow
        ax.annotate(
            "",
            xy=(x_to, connector_y),
            xycoords="data",
            xytext=(x_from, connector_y),
            textcoords="data",
            arrowprops=dict(
                arrowstyle="-|>",
                color="#475569",
                lw=1.6,
                shrinkA=2,
                shrinkB=2,
                mutation_scale=12
            ),
            zorder=4
        )

        # Connector Dataflow Label Pill
        label_w = 0.024
        label_h = 0.020
        mid_x = (x_from + x_to) / 2
        lbl_rect = patches.FancyBboxPatch(
            (mid_x - 0.013, connector_y + 0.015), 0.026, 0.018,
            boxstyle="round,pad=0.002,rounding_size=0.004",
            linewidth=0.6,
            edgecolor="#334155",
            facecolor="#020617",
            zorder=5
        )
        ax.add_patch(lbl_rect)
        ax.text(
            mid_x, connector_y + 0.024,
            connector_labels[i],
            fontsize=5.2,
            fontweight="bold",
            color="#94a3b8",
            ha="center",
            va="center",
            family="monospace",
            zorder=6
        )

    # -------------------------------------------------------------
    # 4. BOTTOM INSTITUTIONAL INVARIANT BAR
    # -------------------------------------------------------------
    bar_rect = patches.FancyBboxPatch(
        (0.030, 0.035), 0.940, 0.095,
        boxstyle="round,pad=0.006,rounding_size=0.012",
        linewidth=1.0,
        edgecolor="#1e293b",
        facecolor="#0b1120",
        zorder=2
    )
    ax.add_patch(bar_rect)

    ax.text(
        0.045, 0.100,
        "CORE RISK & EXECUTION INVARIANTS (ENFORCED IN CODE)",
        fontsize=8.5,
        fontweight="bold",
        color="#38bdf8",
        family="monospace",
        zorder=3
    )

    invariants = [
        "1. Strictly Single Concurrent Trade (Anti-Martingale)",
        "2. Mandatory Hard Stop-Loss on Every Deal",
        "3. Zero Look-Ahead Bias via Strict Lagged Features",
        "4. Spread Sanity Guard (< 3.0 Pips Threshold)",
        "5. Automated Circuit Breaker (-5% Daily / -15% Max DD)",
        "6. Continuous Reconciled P&L via Telegram & MT5 Bridge",
    ]

    col1_x = 0.045
    col2_x = 0.360
    col3_x = 0.675

    ax.text(col1_x, 0.075, invariants[0], fontsize=7.6, color="#cbd5e1", family="sans-serif", zorder=3)
    ax.text(col1_x, 0.050, invariants[1], fontsize=7.6, color="#cbd5e1", family="sans-serif", zorder=3)

    ax.text(col2_x, 0.075, invariants[2], fontsize=7.6, color="#cbd5e1", family="sans-serif", zorder=3)
    ax.text(col2_x, 0.050, invariants[3], fontsize=7.6, color="#cbd5e1", family="sans-serif", zorder=3)

    ax.text(col3_x, 0.075, invariants[4], fontsize=7.6, color="#cbd5e1", family="sans-serif", zorder=3)
    ax.text(col3_x, 0.050, invariants[5], fontsize=7.6, color="#cbd5e1", family="sans-serif", zorder=3)

    # Final Canvas Bounds
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"Successfully generated clean architecture flowchart at: {output_path}")


if __name__ == "__main__":
    create_flowchart()
