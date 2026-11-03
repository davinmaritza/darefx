"""DareFX Remote MT5 Bridge Client for Linux.
Connects Linux native DareFX station to remote MT5 terminal running on VM 126 or any server.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from typing import Any
import requests

from darefx.trading.mt5_bridge import (
    AccountInfo,
    OrderResult,
    OrderType,
    Position,
)

logger = logging.getLogger(__name__)


class RemoteBridge:
    """Bridge adapter connecting to a remote MT5 bridge server over HTTP."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("MT5_REMOTE_URL", "http://127.0.0.1:8888")).rstrip("/")
        self._connected = False
        self.timeout = 5.0

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """Verify connectivity to remote MT5 bridge server."""
        try:
            res = requests.get(f"{self.base_url}/api/health", timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                self._connected = bool(data.get("connected", False))
                if self._connected:
                    logger.info("Connected to remote MT5 bridge at %s (Login: %s)", self.base_url, data.get("login"))
                return self._connected
        except Exception as err:
            logger.warning("Failed to connect to remote MT5 bridge at %s: %s", self.base_url, err)
            self._connected = False
        return self._connected

    def disconnect(self) -> None:
        self._connected = False

    def get_account_info(self) -> AccountInfo:
        """Fetch real-time account capital and margin statistics from remote MT5."""
        res = requests.get(f"{self.base_url}/api/account", timeout=self.timeout)
        res.raise_for_status()
        data = res.json()
        return AccountInfo(
            login=int(data.get("login", 0)),
            currency=str(data.get("currency", "USD")),
            balance=float(data.get("balance", 0.0)),
            equity=float(data.get("equity", 0.0)),
            margin=float(data.get("margin", 0.0)),
            free_margin=float(data.get("margin_free", 0.0)),
            leverage=float(data.get("leverage", 100.0)),
            server=str(data.get("server", "")),
            is_demo=True,
        )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        """Fetch real-time open positions from remote MT5."""
        res = requests.get(f"{self.base_url}/api/positions", timeout=self.timeout)
        res.raise_for_status()
        raw_list = res.json()
        results: list[Position] = []
        for p in raw_list:
            if symbol and p.get("symbol", "").upper() != symbol.upper():
                continue
            order_type = OrderType.BUY if p.get("order_type") == "BUY" else OrderType.SELL
            open_time_str = p.get("open_time", "")
            try:
                open_dt = datetime.fromisoformat(open_time_str)
            except Exception:
                open_dt = datetime.now(timezone.utc)
            results.append(
                Position(
                    ticket=int(p["ticket"]),
                    symbol=str(p["symbol"]),
                    order_type=order_type,
                    volume=float(p["volume"]),
                    open_price=float(p["open_price"]),
                    current_price=float(p["current_price"]),
                    sl=float(p.get("sl", 0.0)),
                    tp=float(p.get("tp", 0.0)),
                    profit=float(p.get("profit", 0.0)),
                    open_time=open_dt,
                )
            )
        return results

    def send_market_order(
        self,
        symbol: str,
        action: OrderType | str,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        current_price: float = 0.0,
        deviation_pips: int = 10,
        comment: str = "darefx",
    ) -> OrderResult:
        """Submit a market order to remote MT5."""
        payload = {
            "symbol": symbol,
            "order_type": action.value if isinstance(action, OrderType) else str(action),
            "volume": volume,
            "sl": sl,
            "tp": tp,
            "comment": comment,
        }
        try:
            res = requests.post(f"{self.base_url}/api/order", json=payload, timeout=10.0)
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                return OrderResult(
                    success=True,
                    ticket=int(data.get("ticket", 0)),
                    volume=float(data.get("volume", volume)),
                    price=float(data.get("price", 0.0)),
                    retcode=int(data.get("retcode", 0)),
                    comment=str(data.get("comment", "")),
                )
            return OrderResult(
                success=False,
                retcode=int(data.get("retcode", -1)),
                comment=str(data.get("comment", "Order failed at remote MT5")),
            )
        except Exception as err:
            logger.error("Exception sending remote order: %s", err)
            return OrderResult(success=False, retcode=-1, comment=str(err))

    def close_position(self, ticket: int) -> bool:
        """Close an open position on remote MT5."""
        try:
            res = requests.post(f"{self.base_url}/api/close", json={"ticket": ticket}, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                return bool(data.get("success", False))
            return False
        except Exception as err:
            logger.error("Exception closing remote position #%d: %s", ticket, err)
            return False
