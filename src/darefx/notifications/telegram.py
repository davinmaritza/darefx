"""Telegram alerting service for DareFX.

Sends instant notifications for:
- Trade Entries (Direction, Lots, Entry Price, SL, TP)
- Trade Exits (Realized PnL, Return %, Exit Reason)
- Circuit Breaker Tripping (PAUSED_DAILY, Emergency SHUTDOWN)
- Daily Performance Digest
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Dispatches trade and risk alerts to a Telegram chat."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        timeout_sec: int = 10,
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout_sec = timeout_sec

    def is_configured(self) -> bool:
        """Check whether valid Telegram credentials are provided."""
        return bool(
            self.bot_token
            and self.chat_id
            and self.bot_token != "your_telegram_bot_token"
            and self.chat_id != "your_telegram_chat_id"
        )

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a formatted text message to the configured Telegram chat."""
        if not self.is_configured():
            logger.debug("Telegram credentials not configured; logging message locally:\n%s", text)
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout_sec)
            if resp.status_code == 200:
                return True
            logger.warning("Telegram API error %d: %s", resp.status_code, resp.text)
            return False
        except requests.RequestException as err:
            logger.error("Failed to connect to Telegram API: %s", err)
            return False

    def notify_trade_opened(
        self,
        direction: str,
        symbol: str,
        lots: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        confidence: float,
    ) -> bool:
        """Alert when a new position is filled."""
        emoji = "🟢 *BUY / LONG*" if direction.upper() in ["BUY", "LONG", "1"] else "🔴 *SELL / SHORT*"
        msg = (
            f"⚡ *DareFX Trade Opened*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Action: {emoji}\n"
            f"Pair: `{symbol}`\n"
            f"Volume: `{lots:.2f} Lots`\n"
            f"Entry Price: `{entry_price:.5f}`\n"
            f"Stop Loss: `{stop_loss:.5f}`\n"
            f"Take Profit: `{take_profit:.5f}`\n"
            f"Model Conviction: `{confidence * 100:.1f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)

    def notify_trade_closed(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        net_pnl_usd: float,
        return_pct: float,
        exit_reason: str,
    ) -> bool:
        """Alert when a position is closed."""
        outcome = "🎉 *PROFIT*" if net_pnl_usd >= 0 else "🛑 *LOSS*"
        msg = (
            f"{outcome} *DareFX Trade Closed*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Pair: `{symbol}` ({direction.upper()})\n"
            f"Entry: `{entry_price:.5f}` ➔ Exit: `{exit_price:.5f}`\n"
            f"Net PnL: *${net_pnl_usd:+.2f}* ({return_pct:+.2f}%)\n"
            f"Exit Reason: `{exit_reason.replace('_', ' ').title()}`\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)

    def notify_circuit_breaker(
        self,
        state: str,
        reason: str,
        current_equity: float,
        drawdown_pct: float,
    ) -> bool:
        """Urgent alert when circuit breaker halts trading."""
        header = "🚨 *EMERGENCY SHUTDOWN*" if state == "SHUTDOWN" else "⚠️ *CIRCUIT BREAKER PAUSED*"
        msg = (
            f"{header}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"State: *{state}*\n"
            f"Reason: _{reason}_\n"
            f"Current Equity: *${current_equity:,.2f}*\n"
            f"Peak Drawdown: *{drawdown_pct:.2f}%*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Action: {'Trading loop aborted. Manual reset required.' if state == 'SHUTDOWN' else 'New entries suspended until next daily session.'}"
        )
        return self.send_message(msg)

    def notify_daily_summary(
        self,
        date_str: str,
        equity: float,
        daily_pnl_usd: float,
        daily_pnl_pct: float,
        open_positions: int,
    ) -> bool:
        """Daily portfolio status digest."""
        pnl_emoji = "📈" if daily_pnl_usd >= 0 else "📉"
        msg = (
            f"📊 *DareFX Daily Digest ({date_str})*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Portfolio Equity: *${equity:,.2f}*\n"
            f"Daily PnL: {pnl_emoji} *${daily_pnl_usd:+.2f}* ({daily_pnl_pct:+.2f}%)\n"
            f"Open Positions: `{open_positions}`\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)
