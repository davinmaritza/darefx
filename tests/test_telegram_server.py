"""Unit tests for DareFX Interactive Telegram Server commands and automations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from darefx.notifications.telegram_server import TelegramServer
from darefx.trading.mt5_bridge import MT5Credentials, MT5Bridge, OrderType, Position


@pytest.fixture
def mock_server() -> TelegramServer:
    server = TelegramServer(bot_token="test_token", chat_id="123456789")
    server.send_reply = MagicMock(return_value=True)  # type: ignore
    return server


def test_telegram_server_keyboard(mock_server: TelegramServer) -> None:
    kb = mock_server.get_keyboard()
    assert "keyboard" in kb
    texts = [btn["text"] for row in kb["keyboard"] for btn in row]
    assert "📰 Kalender Berita" in texts
    assert "🤖 Analisis AI" in texts
    assert "📊 Cek Status" in texts


def test_telegram_server_handle_news(mock_server: TelegramServer) -> None:
    mock_events = [
        {
            "title": "US Non-Farm Payrolls",
            "country": "USD",
            "currency": "USD",
            "impact": "High",
            "datetime_wib": None,
        }
    ]

    with patch("darefx.risk.news_filter.EconomicNewsFilter.is_news_freeze", return_value=(False, "Clear")):
        with patch("darefx.risk.news_filter.EconomicNewsFilter.get_upcoming_events", return_value=mock_events):
            mock_server.handle_message("/news", 123456789)
            assert mock_server.send_reply.called
            sent_text = mock_server.send_reply.call_args[0][1]
            assert "KALENDER BERITA" in sent_text
            assert "Non-Farm Payrolls" in sent_text
            assert "CLEAR" in sent_text


def test_telegram_server_handle_status_shows_news_guard(mock_server: TelegramServer) -> None:
    with patch("darefx.risk.news_filter.EconomicNewsFilter.is_news_freeze", return_value=(True, "High Impact USD")):
        mock_server.handle_message("/status", 123456789)
        assert mock_server.send_reply.called
        sent_text = mock_server.send_reply.call_args[0][1]
        assert "News Guard" in sent_text
        assert "FREEZE" in sent_text


def test_telegram_server_check_breakeven_auto(mock_server: TelegramServer) -> None:
    sim_bridge = MT5Bridge(credentials=MT5Credentials(simulation_mode=True))
    sim_bridge.connect()
    # Mock breakeven returning an updated order
    mock_updated = [{"ticket": 1001, "new_sl": 1.08600, "floating_pips": 16.5}]

    mock_server.executor.check_and_apply_breakeven = MagicMock(return_value=mock_updated)  # type: ignore
    mock_server.check_breakeven_auto()

    assert mock_server.send_reply.called
    sent_text = mock_server.send_reply.call_args[0][1]
    assert "PROTEKSI BREAK-EVEN TERPASANG" in sent_text
    assert "#1001" in sent_text
    assert "+16.5 pips" in sent_text
