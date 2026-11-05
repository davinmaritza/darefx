"""Unified Cross-Asset Portfolio Risk Governor.

Enforces cross-market capital limits across Forex (MT5), Crypto (CCXT), and Stocks (Alpaca):
1. Maximum concurrent global positions (e.g. max 5 trades)
2. Per-asset class exposure caps (e.g. max 2 Forex, max 2 Crypto, max 2 Equities)
3. Cumulative capital risk bounds
4. Signal ranking and prioritization under capacity constraints
5. Directional hedging / duplicate symbol prevention
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from darefx.risk.circuit_breaker import CircuitBreaker
from darefx.trading.mt5_bridge import OrderType, Position

logger = logging.getLogger(__name__)


class AssetClass(StrEnum):
    """Supported market asset classes."""
    FOREX = "forex"
    CRYPTO = "crypto"
    STOCKS = "stocks"


@dataclass
class SignalCandidate:
    """Standardized trading signal candidate from any asset screener."""
    asset_class: AssetClass
    symbol: str
    action: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    adx: float = 0.0
    atr: float = 0.0
    risk_reward_ratio: float = 0.0
    reasoning: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def score(self) -> float:
        """Composite priority ranking score."""
        rr_component = min(max(self.risk_reward_ratio, 1.0), 3.0) / 3.0
        return (self.confidence * 0.7) + (rr_component * 0.3)


@dataclass
class PortfolioGovernorConfig:
    """Risk constraints and position caps across asset classes."""
    max_total_positions: int = 5
    max_positions_per_asset: dict[str, int] = field(
        default_factory=lambda: {
            "forex": 2,
            "crypto": 2,
            "stocks": 2,
        }
    )
    max_portfolio_risk_pct: float = 5.0
    risk_per_trade_pct: float = 1.0
    min_confidence_threshold: float = 0.40
    min_adx: float = 20.0
    allow_hedging: bool = False


class PortfolioGovernor:
    """Manages cross-asset exposure limits and filters candidate signals."""

    def __init__(
        self,
        config: PortfolioGovernorConfig | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.config = config or PortfolioGovernorConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    @staticmethod
    def classify_symbol(symbol: str) -> AssetClass:
        """Infer the asset class from symbol formatting."""
        sym = symbol.upper().strip()
        crypto_ends = ("USDT", "BUSD")
        crypto_coins = ("BTC", "ETH", "SOL", "BNB")
        if "/" in sym or any(sym.endswith(e) for e in crypto_ends) or sym in crypto_coins:
            return AssetClass.CRYPTO
        if len(sym) == 6 and not any(char.isdigit() for char in sym):
            return AssetClass.FOREX
        is_fx_prefix = sym.startswith(("EUR", "USD", "GBP"))
        if (sym.endswith("=X") or is_fx_prefix) and ("/" not in sym and not sym.endswith("USDT")):
            return AssetClass.FOREX
        return AssetClass.STOCKS

    def can_open_trade(
        self,
        candidate: SignalCandidate,
        current_positions: list[Position],
        current_equity: float = 10_000.0,
    ) -> tuple[bool, str]:
        """Verify whether a candidate trade complies with global risk constraints."""
        # 1. Circuit Breaker validation
        if self.circuit_breaker:
            allowed, cb_reason = self.circuit_breaker.can_open_new_trade()
            if not allowed:
                return False, f"Blocked by Circuit Breaker: {cb_reason}"

        # 2. Minimum signal confidence
        if candidate.confidence < self.config.min_confidence_threshold:
            thresh_pct = self.config.min_confidence_threshold * 100
            cand_pct = candidate.confidence * 100
            return False, f"Confidence {cand_pct:.1f}% below threshold {thresh_pct:.1f}%"

        # 3. Minimum trend strength
        if candidate.adx > 0 and candidate.adx < self.config.min_adx:
            return (
                False,
                f"ADX trend strength {candidate.adx:.1f} below minimum {self.config.min_adx:.1f}",
            )

        # 4. Total concurrent positions cap
        if len(current_positions) >= self.config.max_total_positions:
            cap = self.config.max_total_positions
            return False, f"Global position cap reached ({len(current_positions)}/{cap})"

        # 5. Duplicate or conflicting symbol check
        norm_sym = candidate.symbol.replace("/", "").replace("=X", "").upper()
        for p in current_positions:
            p_sym = p.symbol.replace("/", "").replace("=X", "").upper()
            if p_sym == norm_sym and not self.config.allow_hedging:
                return False, f"Active position already open for {candidate.symbol}"

        # 6. Per-asset class position cap
        asset_key = candidate.asset_class.value
        max_asset_positions = self.config.max_positions_per_asset.get(asset_key, 2)
        asset_positions_count = sum(
            1 for p in current_positions if self.classify_symbol(p.symbol) == candidate.asset_class
        )
        if asset_positions_count >= max_asset_positions:
            label = asset_key.upper()
            msg = f"Asset cap for {label} reached ({asset_positions_count}/{max_asset_positions})"
            return False, msg

        # 7. Total portfolio risk capital limit
        active_risk_pct = len(current_positions) * self.config.risk_per_trade_pct
        trade_risk = self.config.risk_per_trade_pct
        max_risk = self.config.max_portfolio_risk_pct
        if active_risk_pct + trade_risk > max_risk:
            err = (
                f"Portfolio risk limit exceeded ({active_risk_pct:.1f}% + {trade_risk:.1f}% > "
                f"{max_risk:.1f}%)"
            )
            return False, err



        return True, "Approved by Portfolio Risk Governor"

    def rank_and_filter(
        self,
        candidates: list[SignalCandidate],
        current_positions: list[Position],
        current_equity: float = 10_000.0,
    ) -> list[SignalCandidate]:
        """Rank candidates by score and greedily admit those passing portfolio constraints."""
        sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
        approved: list[SignalCandidate] = []
        simulated_positions = list(current_positions)

        for cand in sorted_candidates:
            ok, reason = self.can_open_trade(
                candidate=cand,
                current_positions=simulated_positions,
                current_equity=current_equity,
            )
            if ok:
                approved.append(cand)
                dummy_pos = Position(
                    ticket=999_000 + len(simulated_positions),
                    symbol=cand.symbol,
                    order_type=OrderType.BUY if cand.action == "BUY" else OrderType.SELL,
                    volume=1.0,
                    open_price=cand.entry_price,
                    current_price=cand.entry_price,
                    sl=cand.stop_loss,
                    tp=cand.take_profit,
                    profit=0.0,
                    open_time=datetime.now(UTC),
                )
                simulated_positions.append(dummy_pos)
            else:
                logger.info("Signal rejected for %s: %s", cand.symbol, reason)

        return approved
