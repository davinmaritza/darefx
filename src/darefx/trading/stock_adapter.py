"""Stock and Equities Execution Adapter for DareFX (Alpaca Markets).

Provides unified equities trading (S&P 500, NASDAQ 100, etc.) supporting
commission-free fractional shares, portfolio margin tracking, and paper trading.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import time
from typing import Any

import pandas as pd
import requests

from darefx.trading.mt5_bridge import (
    AccountInfo,
    OrderResult,
    OrderType,
    Position,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StockCredentials:
    """Credentials for Alpaca stock trading."""
    api_key: str = ""
    secret_key: str = ""
    paper: bool = True
    simulation_mode: bool = False


class StockAdapter:
    """Standardized equities broker adapter matching DareFX bridge interface."""

    def __init__(
        self,
        credentials: StockCredentials | None = None,
        state_file: str | Path | None = None,
    ) -> None:
        if credentials is None:
            api_key = os.getenv("ALPACA_API_KEY", "")
            secret_key = os.getenv("ALPACA_SECRET_KEY", "")
            paper = os.getenv("ALPACA_PAPER", "true").lower() in ("true", "1", "yes")
            simulation = os.getenv("STOCK_SIMULATION", "true" if not api_key else "false").lower() in ("true", "1", "yes")

            credentials = StockCredentials(
                api_key=api_key,
                secret_key=secret_key,
                paper=paper,
                simulation_mode=simulation,
            )

        self.credentials = credentials
        self.state_file = Path(state_file) if state_file else Path("data/stock_simulation_state.json")
        self._connected = False

        self.base_url = (
            "https://paper-api.alpaca.markets"
            if self.credentials.paper
            else "https://api.alpaca.markets"
        )
        self.data_url = "https://data.alpaca.markets/v2"

        # Simulation in-memory state
        self._sim_cash: float = 25_000.0  # Standard pattern day trader minimum
        self._sim_positions: dict[int, Position] = {}
        self._next_sim_ticket: int = 700_001

        self._init_session()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_simulation(self) -> bool:
        return self.credentials.simulation_mode

    def _init_session(self) -> None:
        """Initialize session and verify credentials."""
        if self.credentials.simulation_mode or not self.credentials.api_key:
            self._connected = True
            logger.info("StockAdapter running in SIMULATION / PAPER mode.")
            return

        self.session = requests.Session()
        self.session.headers.update({
            "APCA-API-KEY-ID": self.credentials.api_key,
            "APCA-API-SECRET-KEY": self.credentials.secret_key,
            "Content-Type": "application/json",
        })

        try:
            res = self.session.get(f"{self.base_url}/v2/account", timeout=5.0)
            if res.status_code == 200:
                self._connected = True
                logger.info("Connected to Alpaca %s account.", "Paper" if self.credentials.paper else "Live")
            else:
                logger.warning("Alpaca auth failed (%d): %s", res.status_code, res.text)
                self._connected = False
        except Exception as err:
            logger.warning("Alpaca connection failed: %s, falling back to simulation", err)
            self._connected = True

    def connect(self) -> bool:
        """Verify broker connection."""
        if self.credentials.simulation_mode or not self.credentials.api_key:
            self._connected = True
            return True
        try:
            res = self.session.get(f"{self.base_url}/v2/account", timeout=5.0)
            self._connected = (res.status_code == 200)
            return self._connected
        except Exception:
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._connected = False

    def get_account_info(self) -> AccountInfo:
        """Fetch stock cash balance, portfolio value, and buying power."""
        if self.credentials.simulation_mode or not self.credentials.api_key:
            portfolio_val = self._sim_cash + sum(p.volume * p.current_price for p in self._sim_positions.values())
            used_margin = sum(p.volume * p.current_price * 0.25 for p in self._sim_positions.values())  # 4:1 intraday
            return AccountInfo(
                login=77777777,
                currency="USD",
                balance=self._sim_cash,
                equity=portfolio_val,
                margin=used_margin,
                free_margin=max(0.0, portfolio_val - used_margin),
                leverage=4.0,
                server="ALPACA-SIMULATION",
                is_demo=True,
            )

        try:
            res = self.session.get(f"{self.base_url}/v2/account", timeout=5.0)
            res.raise_for_status()
            data = res.json()

            equity = float(data.get("equity", 0.0))
            cash = float(data.get("cash", 0.0))
            buying_power = float(data.get("buying_power", 0.0))

            return AccountInfo(
                login=int(data.get("account_number", "1").replace("PA", "").replace("CF", "") or 1),
                currency="USD",
                balance=cash,
                equity=equity,
                margin=max(0.0, equity - cash),
                free_margin=buying_power,
                leverage=float(data.get("multiplier", 4.0)),
                server=f"ALPACA-{'PAPER' if self.credentials.paper else 'LIVE'}",
                is_demo=self.credentials.paper,
            )
        except Exception as err:
            logger.error("Failed to fetch Alpaca account info: %s", err)
            return AccountInfo(
                login=0,
                currency="USD",
                balance=0.0,
                equity=0.0,
                margin=0.0,
                free_margin=0.0,
                leverage=4.0,
                server="ALPACA",
                is_demo=True,
            )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        """Fetch active stock holdings."""
        if self.credentials.simulation_mode or not self.credentials.api_key:
            active = list(self._sim_positions.values())
            if symbol:
                active = [p for p in active if p.symbol.upper() == symbol.upper()]
            return active

        positions: list[Position] = []
        try:
            res = self.session.get(f"{self.base_url}/v2/positions", timeout=5.0)
            if res.status_code == 200:
                data = res.json()
                for i, pos in enumerate(data):
                    qty = float(pos.get("qty", 0.0))
                    side = str(pos.get("side", "")).lower()
                    order_type = OrderType.BUY if side == "long" else OrderType.SELL
                    entry_p = float(pos.get("avg_entry_price", 0.0))
                    current_p = float(pos.get("current_price", entry_p))
                    unrealized_pnl = float(pos.get("unrealized_pl", 0.0))

                    positions.append(
                        Position(
                            ticket=200_000 + i,
                            symbol=str(pos.get("symbol", "")),
                            order_type=order_type,
                            volume=qty,
                            open_price=entry_p,
                            current_price=current_p,
                            sl=0.0,
                            tp=0.0,
                            profit=unrealized_pnl,
                            open_time=datetime.now(timezone.utc),
                        )
                    )
        except Exception as err:
            logger.error("Failed to fetch Alpaca positions: %s", err)

        return positions

    def send_market_order(
        self,
        symbol: str,
        order_type: OrderType,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "DareFX-Stock",
    ) -> OrderResult:
        """Execute a market buy or sell order for equities."""
        if volume <= 0:
            return OrderResult(success=False, comment="Invalid volume")

        sym = symbol.upper()

        if self.credentials.simulation_mode or not self.credentials.api_key:
            fill_price = self.get_latest_price(sym)
            ticket = self._next_sim_ticket
            self._next_sim_ticket += 1

            new_pos = Position(
                ticket=ticket,
                symbol=sym,
                order_type=order_type,
                volume=volume,
                open_price=fill_price,
                current_price=fill_price,
                sl=sl,
                tp=tp,
                profit=0.0,
                open_time=datetime.now(timezone.utc),
            )
            cost = volume * fill_price
            if order_type == OrderType.BUY:
                self._sim_cash -= cost
            else:
                self._sim_cash += cost

            self._sim_positions[ticket] = new_pos
            logger.info("SIM STOCK FILLED: #%d %s %s %.2f shares at $%.2f", ticket, order_type.value, sym, volume, fill_price)
            return OrderResult(success=True, ticket=ticket, volume=volume, price=fill_price, comment="Simulation fill")

        try:
            side = "buy" if order_type == OrderType.BUY else "sell"
            payload: dict[str, Any] = {
                "symbol": sym,
                "qty": str(volume),
                "side": side,
                "type": "market",
                "time_in_force": "day",
            }

            res = self.session.post(f"{self.base_url}/v2/orders", json=payload, timeout=5.0)
            if res.status_code in (200, 201):
                order_data = res.json()
                order_id = int(str(order_data.get("id", "0")).replace("-", "")[:8], 16) % 1_000_000
                price = float(order_data.get("filled_avg_price") or self.get_latest_price(sym))
                return OrderResult(success=True, ticket=order_id, volume=volume, price=price, comment="Alpaca executed")
            else:
                return OrderResult(success=False, comment=f"Alpaca rejected: {res.text}")
        except Exception as err:
            logger.error("Stock order execution error: %s", err)
            return OrderResult(success=False, comment=str(err))

    def close_position(self, ticket: int) -> bool:
        """Close an open position by ticket."""
        if self.credentials.simulation_mode or not self.credentials.api_key:
            if ticket in self._sim_positions:
                pos = self._sim_positions.pop(ticket)
                self._sim_cash += pos.volume * pos.current_price
                return True
            return False

        try:
            positions = self.get_positions()
            target = next((p for p in positions if p.ticket == ticket), None)
            if not target:
                return False

            res = self.session.delete(f"{self.base_url}/v2/positions/{target.symbol}", timeout=5.0)
            return res.status_code in (200, 204)
        except Exception as err:
            logger.error("Failed to close stock position #%d: %s", ticket, err)
            return False

    def get_latest_price(self, symbol: str) -> float:
        """Retrieve latest price for a stock symbol."""
        sym = symbol.upper()
        # Fallback table of baseline prices for top stocks
        price_map = {
            "AAPL": 225.50,
            "NVDA": 138.20,
            "MSFT": 415.00,
            "AMZN": 195.40,
            "GOOGL": 172.80,
            "TSLA": 250.00,
            "META": 580.00,
            "AMD": 155.00,
        }
        if sym in price_map:
            return price_map[sym]

        if not self.credentials.simulation_mode and self.credentials.api_key:
            try:
                res = self.session.get(f"{self.data_url}/stocks/{sym}/trades/latest", timeout=3.0)
                if res.status_code == 200:
                    return float(res.json().get("trade", {}).get("p", 100.0))
            except Exception:
                pass
        return 100.0
