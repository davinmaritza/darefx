"""CCXT Crypto Exchange Bridge and Adapter for DareFX.

Provides a unified interface for connecting to cryptocurrency exchanges
(Binance, Bybit, OKX, etc.) via CCXT for spot and USDT-M futures trading,
querying balances, tracking active positions, and executing orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import time
from typing import Any

import pandas as pd

from darefx.trading.mt5_bridge import (
    AccountInfo,
    OrderResult,
    OrderType,
    Position,
)

logger = logging.getLogger(__name__)

try:
    import ccxt  # type: ignore
    HAS_CCXT = True
except (ImportError, ModuleNotFoundError):
    ccxt = None
    HAS_CCXT = False


@dataclass(frozen=True)
class CryptoCredentials:
    """Credentials and connection parameters for CCXT exchanges."""
    exchange_id: str = "binance"
    api_key: str = ""
    secret: str = ""
    password: str = ""  # Required for OKX/Kucoin passphrase
    sandbox: bool = False
    simulation_mode: bool = False
    default_type: str = "future"  # 'spot' or 'future'


class CCXTAdapter:
    """Standardized CCXT adapter matching DareFX bridge interface."""

    def __init__(
        self,
        credentials: CryptoCredentials | None = None,
        state_file: str | Path | None = None,
    ) -> None:
        if credentials is None:
            exchange_id = os.getenv("CRYPTO_EXCHANGE", "binance").lower()
            api_key = os.getenv("CRYPTO_API_KEY", "")
            secret = os.getenv("CRYPTO_SECRET", "")
            password = os.getenv("CRYPTO_PASSWORD", "")
            sandbox = os.getenv("CRYPTO_SANDBOX", "false").lower() in ("true", "1", "yes")
            simulation = os.getenv("CRYPTO_SIMULATION", "true" if not api_key else "false").lower() in ("true", "1", "yes")
            default_type = os.getenv("CRYPTO_DEFAULT_TYPE", "future").lower()

            credentials = CryptoCredentials(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                sandbox=sandbox,
                simulation_mode=simulation,
                default_type=default_type,
            )

        self.credentials = credentials
        self.state_file = Path(state_file) if state_file else Path("data/crypto_simulation_state.json")
        self._connected = False
        self.exchange: Any = None

        # Simulation in-memory state
        self._sim_balance: float = 10_000.0
        self._sim_positions: dict[int, Position] = {}
        self._next_sim_ticket: int = 500_001

        self._init_exchange()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_simulation(self) -> bool:
        return self.credentials.simulation_mode

    def _init_exchange(self) -> None:
        """Instantiate CCXT exchange driver or fallback to simulation."""
        if not HAS_CCXT or self.credentials.simulation_mode or not self.credentials.api_key:
            self._connected = True
            logger.info("CCXTAdapter running in SIMULATION / DRY-RUN mode.")
            return

        try:
            exchange_class = getattr(ccxt, self.credentials.exchange_id, None)
            if exchange_class is None:
                raise ValueError(f"Exchange '{self.credentials.exchange_id}' is not supported by CCXT.")

            params: dict[str, Any] = {
                "apiKey": self.credentials.api_key,
                "secret": self.credentials.secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": self.credentials.default_type,
                },
            }
            if self.credentials.password:
                params["password"] = self.credentials.password

            self.exchange = exchange_class(params)

            if self.credentials.sandbox:
                self.exchange.set_sandbox_mode(True)

            self._connected = True
            logger.info("Initialized CCXT exchange driver for: %s", self.credentials.exchange_id)
        except Exception as err:
            logger.error("Failed to initialize CCXT exchange %s: %s", self.credentials.exchange_id, err)
            self._connected = False

    def connect(self) -> bool:
        """Test and verify API connectivity."""
        if self.credentials.simulation_mode or self.exchange is None:
            self._connected = True
            return True

        try:
            self.exchange.load_markets()
            self._connected = True
            return True
        except Exception as err:
            logger.warning("CCXT connection check failed: %s", err)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close connection sessions."""
        self._connected = False
        if self.exchange:
            try:
                self.exchange.close()
            except Exception:
                pass

    def get_account_info(self) -> AccountInfo:
        """Fetch account balance, margin, and equity."""
        if self.credentials.simulation_mode or self.exchange is None:
            floating_pnl = sum(p.profit for p in self._sim_positions.values())
            used_margin = sum(p.volume * p.open_price * 0.05 for p in self._sim_positions.values())
            equity = self._sim_balance + floating_pnl
            return AccountInfo(
                login=99999999,
                currency="USDT",
                balance=self._sim_balance,
                equity=equity,
                margin=used_margin,
                free_margin=max(0.0, equity - used_margin),
                leverage=20.0,
                server=f"{self.credentials.exchange_id.upper()}-SIMULATION",
                is_demo=True,
            )

        try:
            balance_data = self.exchange.fetch_balance()
            total_usdt = float(balance_data.get("USDT", {}).get("total", 0.0))
            free_usdt = float(balance_data.get("USDT", {}).get("free", 0.0))
            used_usdt = float(balance_data.get("USDT", {}).get("used", 0.0))

            positions = self.get_positions()
            floating_pnl = sum(p.profit for p in positions)
            equity = total_usdt + floating_pnl

            return AccountInfo(
                login=1,
                currency="USDT",
                balance=total_usdt,
                equity=equity,
                margin=used_usdt,
                free_margin=free_usdt,
                leverage=20.0,
                server=f"{self.credentials.exchange_id.upper()}-{self.credentials.default_type.upper()}",
                is_demo=self.credentials.sandbox,
            )
        except Exception as err:
            logger.error("Failed to fetch CCXT account info: %s", err)
            return AccountInfo(
                login=0,
                currency="USDT",
                balance=0.0,
                equity=0.0,
                margin=0.0,
                free_margin=0.0,
                leverage=20.0,
                server=self.credentials.exchange_id.upper(),
                is_demo=True,
            )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        """Fetch open derivative / spot positions."""
        if self.credentials.simulation_mode or self.exchange is None:
            active = list(self._sim_positions.values())
            if symbol:
                norm_sym = symbol.replace("/", "").upper()
                active = [p for p in active if p.symbol.replace("/", "").upper() == norm_sym]
            return active

        positions: list[Position] = []
        try:
            if hasattr(self.exchange, "fetch_positions"):
                symbols = [symbol] if symbol else None
                raw_positions = self.exchange.fetch_positions(symbols)
                for i, raw in enumerate(raw_positions):
                    contracts = float(raw.get("contracts", 0.0) or 0.0)
                    if contracts == 0.0:
                        continue

                    side = str(raw.get("side", "")).lower()
                    order_type = OrderType.BUY if side == "long" else OrderType.SELL
                    raw_sym = str(raw.get("symbol", ""))
                    entry_price = float(raw.get("entryPrice", 0.0) or 0.0)
                    mark_price = float(raw.get("markPrice", entry_price) or entry_price)
                    unrealized_pnl = float(raw.get("unrealizedPnl", 0.0) or 0.0)

                    positions.append(
                        Position(
                            ticket=int(raw.get("id") or (100_000 + i)),
                            symbol=raw_sym,
                            order_type=order_type,
                            volume=contracts,
                            open_price=entry_price,
                            current_price=mark_price,
                            sl=float(raw.get("stopLossPrice", 0.0) or 0.0),
                            tp=float(raw.get("takeProfitPrice", 0.0) or 0.0),
                            profit=unrealized_pnl,
                            open_time=datetime.now(timezone.utc),
                        )
                    )
        except Exception as err:
            logger.error("Failed to fetch CCXT positions: %s", err)

        return positions

    def send_market_order(
        self,
        symbol: str,
        order_type: OrderType,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "DareFX-Crypto",
    ) -> OrderResult:
        """Execute a market buy or sell order."""
        if volume <= 0:
            return OrderResult(success=False, comment="Invalid volume")

        if self.credentials.simulation_mode or self.exchange is None:
            # Simulation order handling
            ticker = self.fetch_ticker(symbol)
            fill_price = ticker.get("last", 100.0) if ticker else 100.0

            ticket = self._next_sim_ticket
            self._next_sim_ticket += 1

            new_pos = Position(
                ticket=ticket,
                symbol=symbol,
                order_type=order_type,
                volume=volume,
                open_price=fill_price,
                current_price=fill_price,
                sl=sl,
                tp=tp,
                profit=0.0,
                open_time=datetime.now(timezone.utc),
            )
            self._sim_positions[ticket] = new_pos
            logger.info("SIM ORDER FILLED: #%d %s %s %.4f at %.2f", ticket, order_type.value, symbol, volume, fill_price)
            return OrderResult(success=True, ticket=ticket, volume=volume, price=fill_price, comment="Simulation fill")

        try:
            side = "buy" if order_type == OrderType.BUY else "sell"
            params: dict[str, Any] = {}
            if sl > 0:
                params["stopLossPrice"] = sl
            if tp > 0:
                params["takeProfitPrice"] = tp

            order = self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=volume,
                params=params,
            )

            fill_price = float(order.get("average") or order.get("price") or 0.0)
            order_id = int(order.get("id") or time.time())

            return OrderResult(
                success=True,
                ticket=order_id,
                volume=volume,
                price=fill_price,
                comment=f"CCXT {self.credentials.exchange_id} fill",
            )
        except Exception as err:
            logger.error("CCXT order placement failed: %s", err)
            return OrderResult(success=False, comment=str(err))

    def close_position(self, ticket: int) -> bool:
        """Close an active position by ticket."""
        if self.credentials.simulation_mode or self.exchange is None:
            if ticket in self._sim_positions:
                pos = self._sim_positions.pop(ticket)
                self._sim_balance += pos.profit
                logger.info("SIM CLOSED: #%d %s profit=%.2f", ticket, pos.symbol, pos.profit)
                return True
            return False

        try:
            positions = self.get_positions()
            target = next((p for p in positions if p.ticket == ticket), None)
            if not target:
                logger.warning("Position #%d not found on exchange to close", ticket)
                return False

            close_side = "sell" if target.order_type == OrderType.BUY else "buy"
            params: dict[str, Any] = {"reduceOnly": True}
            self.exchange.create_order(
                symbol=target.symbol,
                type="market",
                side=close_side,
                amount=target.volume,
                params=params,
            )
            logger.info("Closed CCXT position #%d for %s", ticket, target.symbol)
            return True
        except Exception as err:
            logger.error("Failed to close CCXT position #%d: %s", ticket, err)
            return False

    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """Fetch current bid, ask, and last price."""
        if not HAS_CCXT:
            return {"symbol": symbol, "bid": 100.0, "ask": 100.1, "last": 100.05}

        # Fallback simulator or real exchange fetch
        client = self.exchange or (getattr(ccxt, "binance", None)())
        try:
            return client.fetch_ticker(symbol)
        except Exception:
            return {"symbol": symbol, "bid": 0.0, "ask": 0.0, "last": 0.0}

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "4h",
        limit: int = 100,
    ) -> pd.DataFrame:
        """Fetch candlestick bars into a pandas DataFrame."""
        if not HAS_CCXT:
            return pd.DataFrame()

        client = self.exchange or (getattr(ccxt, "binance", None)({"enableRateLimit": True}))
        try:
            raw_candles = client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(
                raw_candles,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            return df
        except Exception as err:
            logger.error("Failed to fetch OHLCV for %s: %s", symbol, err)
            return pd.DataFrame()
