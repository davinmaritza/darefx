"""MetaApi Cloud Bridge: connects DareFX directly to MetaTrader 5 brokers from Linux."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import threading
from typing import Any

try:
    from metaapi_cloud_sdk import MetaApi
    HAS_METAAPI_PACKAGE = True
except ImportError:
    MetaApi = None
    HAS_METAAPI_PACKAGE = False

from darefx.trading.mt5_bridge import (
    AccountInfo,
    OrderResult,
    OrderType,
    Position,
)

logger = logging.getLogger(__name__)


class AsyncBridgeRunner:
    """Dedicated background event loop runner for async MetaApi SDK."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="MetaApiBridgeRunner",
        )
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro: Any, timeout: float = 45.0) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)

    def stop(self) -> None:
        try:
            if self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
            if self.thread.is_alive():
                self.thread.join(timeout=2.0)
        except Exception as e:
            logger.debug("Error stopping runner loop: %s", e)


class MetaApiBridge:
    """Bridge adapter mediating communication with MetaTrader 5 via MetaApi Cloud."""

    def __init__(
        self,
        token: str | None = None,
        account_id: str | None = None,
        domain: str | None = None,
    ) -> None:
        self.token = token or os.getenv("METAAPI_TOKEN", "")
        self.account_id = account_id or os.getenv("METAAPI_ACCOUNT_ID", "")
        self.domain = domain or os.getenv("METAAPI_DOMAIN", "")
        self._connected = False
        self._runner: AsyncBridgeRunner | None = None
        self._api: Any = None
        self._account: Any = None
        self._connection: Any = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """Connect to MetaApi cloud MT5 account."""
        if not HAS_METAAPI_PACKAGE:
            logger.error("metaapi-cloud-sdk is not installed. Install with 'pip install metaapi-cloud-sdk'.")
            return False

        if not self.token or not self.account_id:
            logger.error("METAAPI_TOKEN and METAAPI_ACCOUNT_ID must be configured.")
            return False

        if self._connected:
            return True

        self._runner = AsyncBridgeRunner()

        async def _async_connect() -> bool:
            try:
                opts = {"domain": self.domain} if self.domain else {}
                self._api = MetaApi(self.token, opts)
                self._account = await self._api.metatrader_account_api.get_account(self.account_id)
                if self._account.state != "DEPLOYED":
                    logger.info("Account %s is not deployed (state: %s). Deploying...", self.account_id, self._account.state)
                    await self._account.deploy()
                    await self._account.wait_deployed(timeout_in_seconds=60)

                await self._account.wait_connected(timeout_in_seconds=60)
                self._connection = self._account.get_rpc_connection()
                await self._connection.connect()
                await self._connection.wait_synchronized(timeout_in_seconds=60)
                logger.info("Successfully connected to MT5 via MetaApi Cloud (Account ID: %s)", self.account_id)
                return True
            except Exception as err:
                logger.error("MetaApi connection failed: %s", err)
                if self._api:
                    self._api.close()
                return False

        try:
            self._connected = bool(self._runner.run(_async_connect(), timeout=70.0))
            return self._connected
        except Exception as err:
            logger.error("MetaApi connect call timed out or failed: %s", err)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if not self._connected and not self._runner:
            return

        async def _async_disconnect() -> None:
            try:
                if self._connection:
                    await self._connection.close()
                if self._api:
                    self._api.close()
            except Exception as e:
                logger.debug("Error during MetaApi disconnect: %s", e)

        if self._runner:
            try:
                self._runner.run(_async_disconnect(), timeout=10.0)
            except Exception:
                pass
            self._runner.stop()
            self._runner = None

        self._connected = False
        self._connection = None
        self._account = None
        self._api = None
        logger.info("MetaApi session closed.")

    def get_account_info(self) -> AccountInfo:
        """Fetch live account balance, equity, and margin."""
        if not self._connected or not self._runner or not self._connection:
            raise ConnectionError("MetaApiBridge is not connected. Call connect() first.")

        async def _async_info() -> AccountInfo:
            info = await self._connection.get_account_information()
            balance = float(info.get("balance", 0.0))
            equity = float(info.get("equity", balance))
            margin = float(info.get("margin", 0.0))
            free_margin = float(info.get("freeMargin", equity))
            leverage = float(info.get("leverage", 100.0))
            server = str(info.get("server", "MetaApi-Live"))
            is_demo = (
                info.get("type") == "DEMO"
                or "demo" in server.lower()
                or not info.get("tradeAllowed", True)
            )

            return AccountInfo(
                login=int(info.get("login", 0)),
                currency=str(info.get("currency", "USD")),
                balance=balance,
                equity=equity,
                margin=margin,
                free_margin=free_margin,
                leverage=leverage,
                server=server,
                is_demo=is_demo,
            )

        return self._runner.run(_async_info())

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        """Query currently active open positions via MetaApi."""
        if not self._connected or not self._runner or not self._connection:
            raise ConnectionError("MetaApiBridge is not connected. Call connect() first.")

        async def _async_positions() -> list[Position]:
            raw_positions = await self._connection.get_positions()
            results: list[Position] = []
            for p in raw_positions:
                pos_symbol = p.get("symbol", "")
                if symbol and pos_symbol.upper() != symbol.upper():
                    continue

                p_type = p.get("type", "POSITION_TYPE_BUY")
                order_type = OrderType.BUY if "BUY" in p_type.upper() else OrderType.SELL

                time_val = p.get("time")
                if isinstance(time_val, datetime):
                    open_time = time_val
                elif isinstance(time_val, str):
                    try:
                        open_time = datetime.fromisoformat(time_val.replace("Z", "+00:00"))
                    except Exception:
                        open_time = datetime.now(timezone.utc)
                else:
                    open_time = datetime.now(timezone.utc)

                results.append(
                    Position(
                        ticket=int(p.get("id", 0)),
                        symbol=pos_symbol,
                        order_type=order_type,
                        volume=float(p.get("volume", 0.0)),
                        open_price=float(p.get("openPrice", 0.0)),
                        current_price=float(p.get("currentPrice", p.get("openPrice", 0.0))),
                        sl=float(p.get("stopLoss") or 0.0),
                        tp=float(p.get("takeProfit") or 0.0),
                        profit=float(p.get("profit", 0.0)),
                        open_time=open_time,
                    )
                )
            return results

        return self._runner.run(_async_positions())

    def send_market_order(
        self,
        symbol: str,
        action: OrderType | str,
        volume: float,
        sl: float,
        tp: float,
        current_price: float = 0.0,
        deviation_pips: int = 10,
        comment: str = "darefx",
    ) -> OrderResult:
        """Submit a protective market order with stop-loss and take-profit."""
        if not self._connected or not self._runner or not self._connection:
            raise ConnectionError("MetaApiBridge is not connected. Call connect() first.")

        action_enum = OrderType(action.upper()) if isinstance(action, str) else action

        async def _async_order() -> OrderResult:
            opts: dict[str, Any] = {
                "comment": comment,
                "slippage": deviation_pips,
            }
            try:
                if action_enum == OrderType.BUY:
                    resp = await self._connection.create_market_buy_order(
                        symbol=symbol,
                        volume=float(volume),
                        stop_loss=float(sl) if sl > 0 else None,
                        take_profit=float(tp) if tp > 0 else None,
                        options=opts,
                    )
                else:
                    resp = await self._connection.create_market_sell_order(
                        symbol=symbol,
                        volume=float(volume),
                        stop_loss=float(sl) if sl > 0 else None,
                        take_profit=float(tp) if tp > 0 else None,
                        options=opts,
                    )

                retcode = int(resp.get("numericCode", 10009))
                string_code = resp.get("stringCode", "ERR_NO_ERROR")
                success = (retcode == 10009 or string_code == "ERR_NO_ERROR")
                ticket = int(resp.get("orderId") or resp.get("positionId") or 0)
                msg = resp.get("message", "")

                return OrderResult(
                    success=success,
                    ticket=ticket,
                    volume=volume,
                    price=current_price,
                    retcode=retcode,
                    comment=f"MetaApi: {string_code} - {msg}",
                )
            except Exception as err:
                logger.error("MetaApi order execution failed: %s", err)
                return OrderResult(
                    success=False,
                    ticket=0,
                    volume=volume,
                    price=current_price,
                    retcode=-1,
                    comment=f"Execution error: {err}",
                )

        return self._runner.run(_async_order())

    def close_position(self, ticket: int, close_price: float = 0.0) -> OrderResult:
        """Close an active open position by ticket."""
        if not self._connected or not self._runner or not self._connection:
            raise ConnectionError("MetaApiBridge is not connected. Call connect() first.")

        async def _async_close() -> OrderResult:
            try:
                resp = await self._connection.close_position(str(ticket))
                retcode = int(resp.get("numericCode", 10009))
                string_code = resp.get("stringCode", "ERR_NO_ERROR")
                success = (retcode == 10009 or string_code == "ERR_NO_ERROR")
                msg = resp.get("message", "")

                return OrderResult(
                    success=success,
                    ticket=ticket,
                    price=close_price,
                    retcode=retcode,
                    comment=f"MetaApi Close: {string_code} - {msg}",
                )
            except Exception as err:
                logger.error("MetaApi close position failed: %s", err)
                return OrderResult(
                    success=False,
                    ticket=ticket,
                    price=close_price,
                    retcode=-1,
                    comment=f"Close error: {err}",
                )

        return self._runner.run(_async_close())
