# Forex 101 for Developers

This document covers foreign exchange mechanics for developers building quantitative trading systems with zero trading background.

---

## 1. What Forex Is

Foreign exchange (Forex or FX) is the global decentralized market for exchanging national currencies. 

- **Decentralized Over-the-Counter (OTC)**: Unlike the New York Stock Exchange or NASDAQ, forex has no central physical exchange or clearinghouse. Banks, financial institutions, brokers, and retail traders trade directly through an electronic interbank network.
- **Trading Volume**: Global forex turnover averages $7.5 trillion per day (Bank for International Settlements, 2022 Triennial Survey). By comparison, the combined global equity markets trade roughly $500 billion daily.
- **Operating Schedule (24/5)**: The forex market operates continuously 24 hours a day, 5 days a week. Trading begins Sunday at 22:00 UTC (Sydney open) and ends Friday at 22:00 UTC (New York close).
- **Four Trading Sessions**:
  
| Session | Primary Financial Hubs | Open (UTC) | Close (UTC) | Market Characteristics |
|---|---|---|---|---|
| Sydney | Sydney, Wellington | 22:00 | 07:00 | Lowest liquidity for EUR/USD. Spreads are wider. |
| Tokyo | Tokyo, Singapore, Hong Kong | 00:00 | 09:00 | Moderate liquidity. Driven by Asian commercial flow. |
| London | London, Frankfurt, Zurich | 08:00 | 17:00 | Highest trading volume (~35% global FX). Narrow spreads. |
| New York | New York, Chicago | 13:00 | 22:00 | Heavy volume. Overlaps with London from 13:00 to 17:00 UTC. |

The London-New York overlap (13:00 to 17:00 UTC) produces the highest liquidity, lowest spreads, and greatest intraday price movement for EUR/USD.

---

## 2. Currency Pairs

Currencies always trade in pairs. A forex trade simultaneously purchases one currency and sells another.

### Base and Quote Currency

The pair notation follows the format `BASE/QUOTE`:

$$\text{Base Currency} / \text{Quote Currency}$$

- **Base currency**: The first currency. It represents one unit of merchandise.
- **Quote currency**: The second currency. It represents the price paid in quote currency to acquire one unit of the base currency.

**EUR/USD Example**:
- EUR is the base currency; USD is the quote currency.
- `EUR/USD = 1.0850` means 1 Euro costs 1.0850 US Dollars.
- **Long position (Buy)**: You buy EUR and sell USD. You profit when the exchange rate rises (EUR strengthens against USD).
- **Short position (Sell)**: You sell EUR and buy USD. You profit when the exchange rate falls (EUR weakens against USD).

### Pair Categories

| Category | Definition | Examples | Characteristics |
|---|---|---|---|
| Major | US Dollar paired with another major global currency | EUR/USD, USD/JPY, GBP/USD, USD/CHF, AUD/USD, USD/CAD | Deepest liquidity, lowest spreads (0.1 - 1.5 pips), low slippage |
| Minor (Cross) | Major currencies paired without the US Dollar | EUR/GBP, EUR/JPY, GBP/JPY, EUR/CHF, GBP/AUD | Moderate liquidity, wider spreads (1.5 - 4.0 pips) |
| Exotic | One major currency paired with an emerging economy currency | USD/TRY, USD/ZAR, EUR/PLN, USD/MXN | Low liquidity, wide spreads (10 - 100+ pips), high overnight swap fees, gap risk |

DareFX trades EUR/USD exclusively. EUR/USD provides the tightest spreads, deepest liquidity, and lowest execution costs in the forex market.

---

## 3. Pips and Points

The standard unit of price movement in forex is the **pip** (Percentage in Point).

### Definition for EUR/USD

EUR/USD quotes to 4 or 5 decimal places:
- **1 pip** = $0.0001$ (the 4th decimal place).
- **1 point (pipette)** = $0.00001$ (the 5th decimal place, or $0.1$ of a pip).

```
EUR/USD Quote: 1.08500 -> 1.08553
Change:        +0.00053 = +5.3 pips (53 points)
```

### Pip Value Formula

$$\text{Pip Value (in USD)} = \text{Contract Size (Units)} \times 0.0001$$

Because EUR/USD quotes with USD as the quote currency, the pip value calculates directly in USD without currency conversion.

---

## 4. Lot Sizes

Forex contracts trade in standardized units called **lots**.

| Lot Type | Lot Volume | Units of Base Currency (EUR) | USD Pip Value (EUR/USD) | USD P&L on 50-Pip Move |
|---|---|---|---|---|
| Standard | 1.00 | 100,000 EUR | $10.00 | $500.00 |
| Mini | 0.10 | 10,000 EUR | $1.00 | $50.00 |
| Micro | 0.01 | 1,000 EUR | $0.10 | $5.00 |

### Worked Profit and Loss Calculation

**Scenario A: Long Trade**
- Account balance: $10,000 USD
- Trade: Buy 0.10 lots (mini lot = 10,000 EUR) EUR/USD at 1.08500
- Exit: Sell at 1.09000
- Price change: $1.09000 - 1.08500 = +0.00500 = +50 \text{ pips}$
- P&L:
  $$\text{P&L} = 10,000 \times (1.09000 - 1.08500) = 10,000 \times 0.00500 = +\$50.00 \text{ USD}$$

**Scenario B: Short Trade**
- Account balance: $10,000 USD
- Trade: Sell 0.20 lots (20,000 EUR) EUR/USD at 1.08500
- Exit: Buy back at 1.08900 (price moved against position)
- Price change: $1.08500 - 1.08900 = -0.00400 = -40 \text{ pips}$
- P&L:
  $$\text{P&L} = 20,000 \times (1.08500 - 1.08900) = 20,000 \times (-0.00400) = -\$80.00 \text{ USD}$$

---

## 5. Spread

The spread is the difference between the broker's selling price (Ask) and buying price (Bid).

$$\text{Spread} = \text{Ask Price} - \text{Bid Price}$$

- **Bid**: The price at which the broker buys from you (your sell price).
- **Ask**: The price at which the broker sells to you (your buy price).
- **Spread as a Transaction Cost**: When opening a long position, you buy at the Ask. If you close immediately, you sell at the Bid. The position starts at an unrealized loss equal to the spread.

```
Example EUR/USD Quote:
Bid: 1.08502
Ask: 1.08514
Spread = 1.08514 - 1.08502 = 0.00012 = 1.2 pips
```

### Spread Behavior by Market Condition

| Market Condition | Typical EUR/USD Spread | Root Cause |
|---|---|---|
| London / New York Overlap | 0.2 - 0.8 pips | Peak interbank liquidity, tight competitive quotes |
| Asian Session | 0.8 - 1.8 pips | Lower trade volume in EUR and USD pairs |
| Daily Rollover (21:55 - 22:05 UTC) | 3.0 - 8.0 pips | Interbank settlement transition, temporary book thinning |
| High-Impact News (NFP, CPI, Fed, ECB) | 5.0 - 15.0+ pips | Liquidity providers pull limit orders to manage risk |

### Cumulative Spread Cost

A strategy executing 250 round-trip trades annually at 0.20 lots EUR/USD ($2.00 per pip):
- At 0.5 pip spread: $250 \times (0.5 \times \$2.00) = \$250.00$
- At 2.0 pip spread: $250 \times (2.0 \times \$2.00) = \$1,000.00$

Wide spreads degrade strategy profitability. DareFX tracks spread in real time and suspends trade generation during spread spikes.

---

## 6. Slippage

Slippage is the difference between the requested execution price of an order and the price at which the broker fills it.

$$\text{Slippage} = \text{Fill Price} - \text{Requested Price}$$

### Mechanisms Causing Slippage

1. **Execution Latency**: Network round-trip time between the local DareFX bot (Linux Mint / VPS) and the broker MT5 trade server (typically 10 to 60 ms). In fast markets, price changes during transit.
2. **Book Depth Depletion**: A market order exceeding the liquidity available at the top-of-book fills across multiple price levels.
3. **Price Gaps**: High-impact news releases or weekend market openings create discontinuous jumps between ticks.

### Positive vs. Negative Slippage

- **Negative Slippage**: Buy order requested at 1.08500 fills at 1.08515 (cost increases by 1.5 pips).
- **Positive Slippage**: Sell order requested at 1.08500 fills at 1.08510 (revenue increases by 1.0 pip). Brokers pass positive slippage on genuine ECN/STP execution models.

### Backtesting Rule

Never assume zero slippage in backtests. Backtest models must incorporate a penalty of 1.0 to 2.0 pips per trade to reflect real-world execution conditions.

---

## 7. Leverage and Margin

Financial leverage allows trading positions larger than the cash balance by using borrowed capital from the broker.

### Leverage Ratio and Required Margin

Margin is the collateral required by the broker to open and maintain a position.

$$\text{Required Margin} = \frac{\text{Position Size (Units)} \times \text{Base Currency Price}}{\text{Leverage Ratio}}$$

**Example with 1:100 Leverage**:
- Account balance: $1,000 USD
- Leverage: 1:100
- Maximum position capacity: $1,000 \times 100 = \$100,000$ (1.00 standard lot)
- Open 0.10 lot EUR/USD (10,000 EUR) at EUR/USD = 1.0850:
  $$\text{Required Margin} = \frac{10,000 \times 1.0850}{100} = \frac{10,850}{100} = \$108.50 \text{ USD}$$

### Key Margin Metrics

- **Balance**: Cash in the account, excluding open trade unrealized profit or loss.
- **Equity**: Total current account value including open trade floating P&L:
  $$\text{Equity} = \text{Balance} + \text{Unrealized P&L}$$
- **Used Margin**: Sum of required margins across all open positions.
- **Free Margin**: Capital available to open new trades or absorb drawdowns:
  $$\text{Free Margin} = \text{Equity} - \text{Used Margin}$$
- **Margin Level Percentage**: Health indicator of the trading account:
  $$\text{Margin Level} = \left(\frac{\text{Equity}}{\text{Used Margin}}\right) \times 100\%$$

---

## 8. Margin Call and Stop-Out

Brokers enforce automated liquidation policies when accounts suffer drawdowns under heavy leverage.

### Definitions

- **Margin Call (typically 100% Margin Level)**: Equity equals Used Margin ($Free Margin = \$0$). The broker notifies the account holder and blocks all new position opening. Existing positions remain open.
- **Stop-Out (typically 50% Margin Level on MT5 / Valetax)**: Equity drops below 50% of Used Margin. The broker's execution engine automatically closes open positions at current market prices, starting with the largest losing position, until Margin Level exceeds 50%.

### Margin Level Progression Table

Initial condition: $1,000 USD balance, 1:100 leverage, open 0.80 lots EUR/USD (80,000 EUR) at 1.08500.  
Required Margin: $\frac{80,000 \times 1.08500}{100} = \$868.00$. Pip value: $8.00 USD per pip.

| Price Move | Unrealized P&L | Equity | Used Margin | Free Margin | Margin Level | Account Status |
|---|---|---|---|---|---|---|
| 0 pips | $0.00 | $1,000.00 | $868.00 | $132.00 | 115.2% | Active |
| -16.5 pips | -$132.00 | $868.00 | $868.00 | $0.00 | 100.0% | Margin Call triggered |
| -40 pips | -$320.00 | $680.00 | $868.00 | -$188.00 | 78.3% | Liquidation warning |
| -70.7 pips | -$566.00 | $434.00 | $868.00 | -$434.00 | 50.0% | Stop-Out: Forced liquidation |

A normal intraday move of 71 pips erases 57% of account equity when overleveraged. DareFX limits margin utilization to 5% of balance to keep Margin Level above 2000%.

---

## 9. Swap and Rollover

Forex positions held past 22:00 UTC (17:00 New York time) incur or earn an overnight interest financing fee called **swap** or **rollover**.

### The Interest Rate Differential Mechanism

Currencies carry central bank benchmark rates:
- European Central Bank (ECB) deposit facility rate.
- US Federal Reserve Fed Funds target rate.

When holding a currency pair overnight:
1. You earn interest on the currency you bought (base currency in a long trade).
2. You pay interest on the currency you borrowed (quote currency in a long trade).
3. The broker adds an administrative financing fee (spread markup).

$$\text{Swap} \approx (\text{Interest Rate}_{\text{Bought}} - \text{Interest Rate}_{\text{Borrowed}} - \text{Broker Markup})$$

### Swap Dynamics for EUR/USD

- When US interest rates exceed Eurozone interest rates:
  - Long EUR/USD (buy EUR, borrow USD) pays negative swap daily.
  - Short EUR/USD (sell EUR, buy USD) receives positive swap or low negative swap (depending on broker retail markup).
- **Triple Swap Wednesday**: Forex spot trades settle two business days after trade date ($T+2$). Positions held overnight Wednesday roll settlement from Friday to Monday, spanning the 2-day weekend. Brokers charge or credit 3 days of swap on Wednesday night at 22:00 UTC.

DareFX backtesting incorporates daily swap values directly from broker swap rate tables.

---

## 10. Order Types

Order types determine how the broker execution venue processes entries and exits.

```
                  Above Current Market Price
                  ├── Buy Stop  (Entry: buy on upward breakout)
                  └── Sell Limit (Entry: sell on upward retracement)
                           ▲
                  [ CURRENT MARKET PRICE ]
                           ▼
                  ├── Buy Limit  (Entry: buy on downward dip)
                  └── Sell Stop (Entry: sell on downward breakdown)
                  Below Current Market Price
```

### Order Type Reference Table

| Order Type | Direction | Placement vs Current Price | Execution Trigger | Usage in DareFX |
|---|---|---|---|---|
| Market Buy | Long | Current Ask price | Immediate fill at best available price | Rapid model entry on new daily bar |
| Market Sell | Short | Current Bid price | Immediate fill at best available price | Rapid model entry on new daily bar |
| Buy Limit | Long | Below current market | Price falls to or below specified limit | Fading oversold intraday pullbacks |
| Sell Limit | Short | Above current market | Price rises to or above specified limit | Fading overbought intraday rallies |
| Buy Stop | Long | Above current market | Price rises to or above specified level | Momentum entries on high-probability breakouts |
| Sell Stop | Short | Below current market | Price falls to or below specified level | Momentum entries on downside breakdown |
| Stop-Loss (SL) | Close | Opposite to trade direction | Triggers market order when price reaches risk threshold | Hard protective stop on every opened position |
| Take-Profit (TP) | Close | In direction of profit target | Triggers limit order when price reaches target | Triple barrier upper/lower profit exit |
| Trailing Stop | Close | Behind price at fixed distance | Adjusts stop level upwards (longs) or downwards (shorts) as market advances | Locks in unrealized gains during extended trends |

---

## 11. Why 90% of Retail Traders Lose Money

Regulatory data published by ESMA (Europe) and the CFTC (US) reveals that 70% to 90% of retail forex trading accounts lose money over any 12-month window.

Five structural flaws cause retail failure:

1. **Absence of Quantifiable Edge**: Entering positions based on discretionary pattern reading, social media tips, or unvalidated chart drawings without verifiable statistical expectancy.
2. **Excessive Leverage**: Trading position sizes where an adverse move of 30 to 50 pips wipes out 10% to 30% of capital. Two consecutive bad days induce account ruin.
3. **Behavioral Bias**:
   - Cutting profitable trades early to lock in small psychological wins.
   - Letting losing trades run, widening stop-losses in hopes of mean-reversion.
   - Revenge trading: increasing position size immediately after a loss to recover capital quickly.
4. **Frictional Depletion**: High-frequency scalping where bid-ask spreads, broker commissions, and negative swaps consume edge faster than gross trading gains accrue.
5. **Survivorship Bias**: Public forums showcase rare outlier accounts that gained 500% in a month through reckless 1:500 leverage, hiding the thousands of accounts wiped out using identical risk profiles.

---

## 12. What 'Edge' Means Quantitatively

An edge is a proven statistical advantage that yields positive Expected Value ($EV$) across hundreds of executions after accounting for all market friction.

### Expected Value (EV) Formula

$$\text{EV} = (P_{\text{win}} \times W) - (P_{\text{loss}} \times L) - C$$

Where:
- $P_{\text{win}}$ = Probability of winning trade
- $P_{\text{loss}} = 1 - P_{\text{win}}$ = Probability of losing trade
- $W$ = Average winning trade amount
- $L$ = Average losing trade amount
- $C$ = Average round-trip friction cost (spread + commission + slippage + swap)

### Win Rate vs. Risk-Reward Tradeoff

A profitable trading system does not require a high win rate. Profitability depends on the product of win rate and payoff ratio ($W/L$):

| Win Rate ($P_{\text{win}}$) | Risk-Reward Ratio ($W : L$) | Avg Win ($W$) | Avg Loss ($L$) | EV per Trade (before fees) | Viability |
|---|---|---|---|---|---|
| 35% | 1 : 2.5 | $250 | $100 | $(0.35 \times 250) - (0.65 \times 100) = +\$22.50$ | Profitable |
| 50% | 1 : 1.5 | $150 | $100 | $(0.50 \times 150) - (0.50 \times 100) = +\$25.00$ | Profitable |
| 60% | 1 : 1.0 | $100 | $100 | $(0.60 \times 100) - (0.40 \times 100) = +\$20.00$ | Profitable |
| 75% | 1 : 0.3 | $30 | $100 | $(0.75 \times 30) - (0.25 \times 100) = -\$2.50$ | Losing strategy |

### Sharpe Ratio Benchmark

The Sharpe ratio measures excess return per unit of volatility:

$$\text{Sharpe} = \frac{R_p - R_f}{\sigma_p} \times \sqrt{252}$$

Where $R_p$ is annual strategy return, $R_f$ is risk-free interest rate (US 3-Month T-Bill), and $\sigma_p$ is annualized daily return volatility.

- **Sharpe < 0.5**: Weak performance; returns do not compensate for downside volatility.
- **Sharpe 1.0 - 1.5**: DareFX project target. A consistent, deployable algorithmic model.
- **Sharpe > 2.0**: Rare on daily forex swing strategies; usually signals data leakage, lookahead bias, or test-set overfitting in backtests.

### Statistical Sample Size

Small sample sizes yield false confidence. In a series of 20 trades, a random coin-flip strategy has a 5.7% probability of generating 14 or more wins ($70\%+$ win rate) purely by chance:

$$\text{Standard Error of Win Rate} = \sqrt{\frac{p(1-p)}{N}}$$

- With $N = 30$ trades and $p = 0.55$: Standard error = $9.1\%$. The true win rate lies anywhere between $37\%$ and $73\%$ ($95\%$ confidence interval).
- With $N = 300$ trades and $p = 0.55$: Standard error = $2.9\%$. The true win rate lies between $49.2\%$ and $60.8\%$.

DareFX requires at least 300 out-of-sample trades across walk-forward validation folds before certifying an ML model for live demo execution.

---

## 13. Market Regimes

Forex returns are non-stationary. Price dynamics oscillate between distinct macroeconomic and liquidity environments called **market regimes**.

### The Four Primary Regimes

```
                   High Volatility (High ATR)
                              │
          Breakout / Volatile │ Violent Oscillation /
          Trending Regime     │ Wide Range Regime
                              │
  ────────────────────────────┼────────────────────────────
                              │
          Smooth Persistent   │ Low-Volatility Compression /
          Trend Regime        │ Tight Range Regime
                              │
                    Low Volatility (Low ATR)
  Trend Direction (High ADX) ◄─┴─► Range / Mean-Reverting (Low ADX)
```

| Regime | Technical Indicators | Price Characteristics | Winning Strategy Type | Failing Strategy Type |
|---|---|---|---|---|
| **Trending (Low Volatility)** | ADX > 25, EMAs aligned, ATR stable | Directional drift with small pullbacks | Trend-following, momentum breakouts | Mean-reversion (gets run over) |
| **Trending (High Volatility)** | ADX > 25, expanding ATR, wide bars | Fast violent advances, deep retracements | Wide-stop momentum, trailing stops | Tight stop-loss momentum (stopped out repeatedly) |
| **Ranging (Low Volatility)** | ADX < 20, tight Bollinger Bands, flat EMAs | Price oscillates inside clear horizontal boundaries | Bollinger Band fade, RSI mean-reversion | Trend-following (false breakout whipsaws) |
| **Ranging (High Volatility)** | ADX < 20, expanding ATR, erratic wicks | Large swings without directional continuation | Volatility break strategies | Stationary mean-reversion, breakout systems |

### Why Machine Learning Models Fail Without Regime Awareness

A standard classifier trained on raw indicators without regime context learns contradictory rules:
- An RSI value of 75 in a ranging regime signals a sell (overbought reversal).
- An RSI value of 75 in a strong breakout trend signals a strong buy (momentum continuation).

When regime changes, static models experience extended drawdown. DareFX supplies regime-detecting features directly to LightGBM and XGBoost:
1. **Trend strength**: ADX(14) and directional movement indicators (DMP, DMN).
2. **Volatility regime**: ATR(14) normalized by 50-day ATR moving average, Bollinger Band Width.
3. **Structural alignment**: Exponential Moving Average stack order (EMA20, EMA50, EMA200).
4. **Historical price channel**: 20-day Donchian channel percentile.
