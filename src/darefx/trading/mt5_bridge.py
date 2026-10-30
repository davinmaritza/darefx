"""MetaTrader 5 Bridge and Adapter for DareFX.

Provides a unified interface for connecting to MetaTrader 5 (e.g. Valetax Demo / Live),
querying live account balances and positions, and dispatching execution orders.

Architecture on Linux:
- On native Windows or Wine Python, wraps the official `MetaTrader5` package.
- On Linux Mint where native MT5 binaries are unavailable without a gateway/Wine,
  operates in a robust simulation/dry-run mode or connects to a configured MT5 execution host.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Check if native MetaTrader5 package is installed
try:
    import MetaTrader5 as mt5  # type: ignore
    HAS_MT5_PACKAGE = True
except (ImportError, ModuleNotFoundError):
    mt5 = None
    HAS_MT5_PACKAGE = False


class OrderType(str, Enum):
    """Order direction."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class MT5Credentials:
    """Credentials and connection parameters for MT5."""
    login: int = 0
    password: str = ""
    server: str = "Valetax-Demo"
    path: str = ""
    timeout: int = 60_000
    simulation_mode: bool = False
    metaapi_token: str = ""
    metaapi_account_id: str = ""


@dataclass
class AccountInfo:
    """Trading account snapshot."""
    login: int
    currency: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: float
    server: str
    is_demo: bool = True


@dataclass
class Position:
    """Active open position in MT5."""
    ticket: int
    symbol: str
    order_type: OrderType
    volume: float
    open_price: float
    current_price: float
    sl: float
    tp: float
    profit: float
    open_time: datetime


@dataclass
class OrderResult:
    """Outcome of an order execution request."""
    success: bool
    ticket: int = 0
    volume: float = 0.0
    price: float = 0.0
    retcode: int = 0
    comment: str = ""


class MT5Bridge:
    """Bridge adapter mediating communication with MetaTrader 5 terminal."""

    def __init__(
        self,
        credentials: MT5Credentials | None = None,
        state_file: str | Path | None = None,
    ) -> None:
        if credentials is None:
            # Attempt to read from environment variables
            login = int(os.getenv("MT5_LOGIN", "0"))
            password = os.getenv("MT5_PASSWORD", "")
            server = os.getenv("MT5_SERVER", "Valetax-Demo")
            path = os.getenv("MT5_PATH", "")
            simulation = os.getenv("MT5_SIMULATION", "true").lower() in ("1", "true", "yes")
            metaapi_token = os.getenv("METAAPI_TOKEN", "")
            metaapi_account_id = os.getenv("METAAPI_ACCOUNT_ID", "")
            self.credentials = MT5Credentials(
                login=login,
                password=password,
                server=server,
                path=path,
                simulation_mode=simulation,
                metaapi_token=metaapi_token,
                metaapi_account_id=metaapi_account_id,
            )
            default_path = os.getenv("SIMULATED_STATE_FILE", "data/simulated_positions.json")
            self._state_file: Path | None = Path(state_file) if state_file else Path(default_path)
        else:
            self.credentials = credentials
            if state_file is not None:
                self._state_file = Path(state_file)
            elif os.getenv("SIMULATED_STATE_FILE"):
                self._state_file = Path(os.environ["SIMULATED_STATE_FILE"])
            else:
                self._state_file = None

        self._connected = False
        self._metaapi_bridge: Any = None

        # Check if MetaApi cloud bridge should be utilized
        m_tok = self.credentials.metaapi_token or os.getenv("METAAPI_TOKEN", "")
        m_acc = self.credentials.metaapi_account_id or os.getenv("METAAPI_ACCOUNT_ID", "")
        if not self.credentials.simulation_mode and m_tok and m_acc:
            try:
                from darefx.trading.metaapi_bridge import MetaApiBridge
                self._metaapi_bridge = MetaApiBridge(token=m_tok, account_id=m_acc)
                logger.info("Initialized MetaApi Cloud Bridge for MT5 account %s", m_acc)
            except Exception as err:
                logger.warning("Failed to initialize MetaApi bridge: %s", err)

        self._simulated_positions: dict[int, Position] = {}
        self._ticket_counter = 100_001
        self._simulated_balance = 10_000.0
        self._load_simulated_state()

    def _load_simulated_state(self) -> None:
        """Load simulated positions and balance from disk."""
        if not self._state_file or not self._state_file.exists():
            return
        try:
            with open(self._state_file, "r") as f:
                data = json.load(f)
            self._simulated_balance = float(data.get("balance", 10_000.0))
            self._ticket_counter = int(data.get("next_ticket", 100_001))
            pos_list = data.get("positions", [])
            self._simulated_positions = {}
            for p in pos_list:
                pos = Position(
                    ticket=int(p["ticket"]),
                    symbol=p["symbol"],
                    order_type=OrderType(p["order_type"]),
                    volume=float(p["volume"]),
                    open_price=float(p["open_price"]),
                    current_price=float(p.get("current_price", p["open_price"])),
                    sl=float(p["sl"]),
                    tp=float(p["tp"]),
                    profit=float(p.get("profit", 0.0)),
                    open_time=datetime.fromisoformat(p["open_time"]),
                )
                self._simulated_positions[pos.ticket] = pos
        except Exception as err:
            logger.warning("Failed to load simulated state: %s", err)

    def _save_simulated_state(self) -> None:
        """Persist simulated positions and balance to disk."""
        if not self._state_file:
            return
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            pos_list = [
                {
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "order_type": p.order_type.value,
                    "volume": p.volume,
                    "open_price": p.open_price,
                    "current_price": p.current_price,
                    "sl": p.sl,
                    "tp": p.tp,
                    "profit": p.profit,
                    "open_time": p.open_time.isoformat(),
                }
                for p in self._simulated_positions.values()
            ]
            data = {
                "balance": self._simulated_balance,
                "next_ticket": self._ticket_counter,
                "positions": pos_list,
            }
            with open(self._state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as err:
            logger.warning("Failed to save simulated state: %s", err)

    @property
    def is_connected(self) -> bool:
        """Connection status."""
        return self._connected

    def connect(self) -> bool:
        """Initialize connection to MetaTrader 5."""
        if self._metaapi_bridge:
            logger.info("Connecting to MT5 broker via MetaApi Cloud Bridge...")
            self._connected = self._metaapi_bridge.connect()
            return self._connected

        if not HAS_MT5_PACKAGE or self.credentials.simulation_mode:
            logger.info("Initializing MT5Bridge in SIMULATION / PAPER mode (Linux native).")
            self._connected = True
            return True

        # Native MetaTrader 5 initialization
        init_kwargs: dict[str, Any] = {"timeout": self.credentials.timeout}
        if self.credentials.path:
            init_kwargs["path"] = self.credentials.path

        if not mt5.initialize(**init_kwargs):
            err = mt5.last_error()
            logger.error("MetaTrader5 initialization failed: %s", err)
            return False

        if self.credentials.login > 0:
            authorized = mt5.login(
                login=self.credentials.login,
                password=self.credentials.password,
                server=self.credentials.server,
                timeout=self.credentials.timeout,
            )
            if not authorized:
                err = mt5.last_error()
                logger.error("MetaTrader5 login failed for account %d: %s", self.credentials.login, err)
                mt5.shutdown()
                return False

        self._connected = True
        logger.info("Successfully authenticated to MT5 server: %s (Account: %d)",
                    self.credentials.server, self.credentials.login)
        return True

    def disconnect(self) -> None:
        """Disconnect and terminate MT5 bridge session."""
        if self._metaapi_bridge:
            self._metaapi_bridge.disconnect()
            self._connected = False
            return

        if self._connected and HAS_MT5_PACKAGE and not self.credentials.simulation_mode:
            mt5.shutdown()
        self._connected = False
        logger.info("MT5 bridge session closed.")

    def get_account_info(self) -> AccountInfo:
        """Fetch real-time account capital and margin statistics."""
        if not self._connected:
            raise ConnectionError("MT5Bridge is not connected. Call connect() first.")

        if self._metaapi_bridge:
            return self._metaapi_bridge.get_account_info()

        if not HAS_MT5_PACKAGE or self.credentials.simulation_mode:
            # Return simulated paper account statistics
            unrealized_pnl = sum(p.profit for p in self._simulated_positions.values())
            equity = self._simulated_balance + unrealized_pnl
            return AccountInfo(
                login=self.credentials.login or 999999,
                currency="USD",
                balance=self._simulated_balance,
                equity=equity,
                margin=0.0,
                free_margin=equity,
                leverage=100.0,
                server=self.credentials.server,
                is_demo=True,
            )

        info = mt5.account_info()
        if info is None:
            err = mt5.last_error()
            raise RuntimeError(f"Failed to query MT5 account info: {err}")

        return AccountInfo(
            login=info.login,
            currency=info.currency,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            leverage=float(info.leverage),
            server=info.server,
            is_demo=(info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO),
        )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        """Query currently active open positions."""
        if not self._connected:
            raise ConnectionError("MT5Bridge is not connected. Call connect() first.")

        if self._metaapi_bridge:
            return self._metaapi_bridge.get_positions(symbol=symbol)

        if not HAS_MT5_PACKAGE or self.credentials.simulation_mode:
            self._load_simulated_state()
            positions = list(self._simulated_positions.values())
            for p in positions:
                if p.order_type == OrderType.BUY:
                    pips = (p.current_price - p.open_price) / 0.0001
                else:
                    pips = (p.open_price - p.current_price) / 0.0001
                p.profit = pips * 10.0 * p.volume
            if symbol:
                positions = [p for p in positions if p.symbol.upper() == symbol.upper()]
            return positions

        mt5_positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if mt5_positions is None:
            return []

        results: list[Position] = []
        for pos in mt5_positions:
            order_type = OrderType.BUY if pos.type == mt5.ORDER_TYPE_BUY else OrderType.SELL
            results.append(
                Position(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    order_type=order_type,
                    volume=pos.volume,
                    open_price=pos.price_open,
                    current_price=pos.price_current,
                    sl=pos.sl,
                    tp=pos.tp,
                    profit=pos.profit,
                    open_time=datetime.fromtimestamp(pos.time, tz=timezone.utc),
                )
            )
        return results

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
        if not self._connected:
            raise ConnectionError("MT5Bridge is not connected. Call connect() first.")

        if self._metaapi_bridge:
            return self._metaapi_bridge.send_market_order(
                symbol=symbol,
                action=action,
                volume=volume,
                sl=sl,
                tp=tp,
                current_price=current_price,
                deviation_pips=deviation_pips,
                comment=comment,
            )

        action_enum = OrderType(action.upper()) if isinstance(action, str) else action

        if not HAS_MT5_PACKAGE or self.credentials.simulation_mode:
            ticket = self._ticket_counter
            self._ticket_counter += 1
            exec_price = current_price if current_price > 0 else 1.08500

            pos = Position(
                ticket=ticket,
                symbol=symbol,
                order_type=action_enum,
                volume=volume,
                open_price=exec_price,
                current_price=exec_price,
                sl=sl,
                tp=tp,
                profit=0.0,
                open_time=datetime.now(timezone.utc),
            )
            self._simulated_positions[ticket] = pos
            self._save_simulated_state()
            logger.info("[SIMULATION] Executed %s %s %.2f lots @ %.5f (SL: %.5f, TP: %.5f) Ticket: #%d",
                        action_enum.value, symbol, volume, exec_price, sl, tp, ticket)
            return OrderResult(
                success=True,
                ticket=ticket,
                volume=volume,
                price=exec_price,
                retcode=10009,  # MT5 TRADE_RETCODE_DONE
                comment=f"Simulated execution: {comment}",
            )

        # Real MT5 execution
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(success=False, retcode=-1, comment=f"Could not retrieve tick for {symbol}")

        if action_enum == OrderType.BUY:
            mt5_order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        else:
            mt5_order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": mt5_order_type,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": deviation_pips * 10,  # convert pips to points
            "magic": 20261029,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err_code = result.retcode if result else -1
            err_comment = result.comment if result else str(mt5.last_error())
            logger.error("Order failed: %s (Retcode: %s)", err_comment, err_code)
            return OrderResult(success=False, retcode=err_code, comment=err_comment)

        logger.info("Order executed successfully: #%d %s %.2f lots @ %.5f",
                    result.order, action_enum.value, volume, result.price)
        return OrderResult(
            success=True,
            ticket=result.order,
            volume=result.volume,
            price=result.price,
            retcode=result.retcode,
            comment=result.comment,
        )

    def close_position(self, ticket: int, close_price: float = 0.0) -> OrderResult:
        """Close an active open position by ticket."""
        if not self._connected:
            raise ConnectionError("MT5Bridge is not connected. Call connect() first.")

        if self._metaapi_bridge:
            return self._metaapi_bridge.close_position(ticket=ticket, close_price=close_price)

        if not HAS_MT5_PACKAGE or self.credentials.simulation_mode:
            if ticket not in self._simulated_positions:
                return OrderResult(success=False, comment=f"Ticket #{ticket} not found.")

            pos = self._simulated_positions.pop(ticket)
            exit_price = close_price if close_price > 0 else pos.open_price
            pnl_pips = (exit_price - pos.open_price) * 10_000 if pos.order_type == OrderType.BUY else (pos.open_price - exit_price) * 10_000
            realized_pnl = pnl_pips * 10.0 * pos.volume
            self._simulated_balance += realized_pnl
            self._save_simulated_state()

            logger.info("[SIMULATION] Closed ticket #%d %s @ %.5f (PnL: $%.2f)",
                        ticket, pos.symbol, exit_price, realized_pnl)
            return OrderResult(
                success=True,
                ticket=ticket,
                volume=pos.volume,
                price=exit_price,
                retcode=10009,
                comment=f"Closed with PnL: ${realized_pnl:.2f}",
            )

        # Real MT5 position close
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return OrderResult(success=False, comment=f"Ticket #{ticket} not found in MT5.")

        pos = positions[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return OrderResult(success=False, comment=f"Could not retrieve tick for {pos.symbol}")

        if pos.type == mt5.ORDER_TYPE_BUY:
            close_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            close_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "price": price,
            "deviation": 20,
            "magic": 20261029,
            "comment": f"close #{ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err_code = result.retcode if result else -1
            err_comment = result.comment if result else str(mt5.last_error())
            return OrderResult(success=False, retcode=err_code, comment=err_comment)

        return OrderResult(
            success=True,
            ticket=result.order,
            volume=result.volume,
            price=result.price,
            retcode=result.retcode,
            comment=result.comment,
        )
